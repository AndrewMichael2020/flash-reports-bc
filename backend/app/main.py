"""
FastAPI application main entry point.
Implements endpoints for the Crimewatch Intel backend.
"""
import os
import sys
# Ensure repository root is on sys.path so 'backend' package imports resolve when running uvicorn from repo root / different working dir
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import asyncio
import re
from urllib.parse import urlparse
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone
from starlette.responses import Response
from fastapi.responses import JSONResponse, HTMLResponse

from app.db import get_db, engine, Base
from app.models import Source, ArticleRaw, IncidentEnriched
from app.schemas import (
    RefreshRequest, RefreshResponse,
    IncidentsResponse, IncidentResponse,
    CoordinatesSchema, GraphResponse, GraphNode, GraphLink,
    MapResponse, MapMarker
)
from app.ingestion.rcmp_parser import RCMPParser
from app.ingestion.wordpress_parser import WordPressParser
from app.ingestion.municipal_list_parser import MunicipalListParser
from app.enrichment.gemini_enricher import GeminiEnricher
from app.config_loader import sync_sources_to_db
from app.logging_config import setup_logging, get_logger

from contextlib import asynccontextmanager

# Configuration constants
SCRAPER_TIMEOUT_SECONDS = 30.0  # Timeout per source when fetching articles

# Set up logging
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

# Determine environment (dev/prod) for CORS behavior
ENV = os.getenv("ENV", "dev").lower()

# Read explicit frontend origins from env (comma separated)
frontend_origins_env = os.getenv("FRONTEND_ORIGINS", "")
parsed_frontend_origins = [o.strip() for o in frontend_origins_env.split(",") if o.strip()]

base_allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

codespace_name = os.getenv("CODESPACE_NAME")
frontend_port = os.getenv("FRONTEND_PORT", "3000")
port_forwarding_domain = os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
codespace_origin = None

if codespace_name:
    codespace_origin = f"https://{codespace_name}-{frontend_port}.{port_forwarding_domain}"
    # Add computed codespace origin to explicit parsed list so it's matched explicitly
    parsed_frontend_origins.append(codespace_origin)

# Combine allowed origins (explicit + base)
allowed_origins = list(dict.fromkeys(base_allowed_origins + parsed_frontend_origins))


# Dev-only permissive CORS escape hatch for quick debugging in Codespaces
DEV_PERMISSIVE_CORS = os.getenv("DEV_PERMISSIVE_CORS", "").lower() in ("1", "true", "yes")

# In dev, allow GitHub Codespaces-style hosts via regex by default (configurable)
cors_allow_origin_regex = None
if ENV == "dev":
    cors_allow_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", r"https://.*\.app\.github\.dev")

# If no explicit origins configured and we are in dev, fallback to allowing localhost set
if ENV == "dev" and not (allowed_origins or cors_allow_origin_regex):
    allowed_origins = base_allowed_origins

# Apply permissive dev override if requested (temporary only)
if ENV == "dev" and DEV_PERMISSIVE_CORS:
    logger.warning("DEV_PERMISSIVE_CORS enabled — allowing all origins (Access-Control-Allow-Origin: *). Do NOT enable in production.")
    allow_credentials = False
    allowed_origins = ["*"]
else:
    # If any wildcard '*' in env origins, force wildcard behaviour (disable credentials)
    if "*" in allowed_origins:
        allow_credentials = False
    else:
        allow_credentials = True

# Create tables on startup (for development; in prod use migrations)
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown."""
    logger.info("Starting Crimewatch Intel Backend")
    
    # NOTE: Source sync deliberately not performed at startup.
    # Sources are synced only when the /api/refresh endpoint is invoked.
#     # Startup: sync database sources from config file
#     db = next(get_db())
#     
#     try:
#         # Sync sources from config/sources.yaml to database
#         synced_count = sync_sources_to_db(db, force_update=False)
#         logger.info(f"Synced {synced_count} sources from configuration to database")
#     except Exception as e:
#         logger.warning(f"Failed to sync sources from config: {e}")
#         logger.warning("Backend will continue with existing database sources")
#     finally:
#         db.close()
    
    yield
    
    logger.info("Shutting down Crimewatch Intel Backend")
    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="Crimewatch Intel Backend",
    description="Backend API for Crimewatch Intel police newsroom aggregator",
    version="2.0.0",
    lifespan=lifespan
)

# Log the CORS settings for debugging
logger.info(f"CORS allowed_origins: {allowed_origins}")
logger.info(f"CORS allow_origin_regex: {cors_allow_origin_regex}")
logger.info(f"CORS allow_credentials: {allow_credentials}")
if codespace_origin:
    logger.info(f"Computed codespace_origin: {codespace_origin} (ensure CODESPACE_NAME is set in Codespace env for explicit matching)")

# CORS middleware to allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=cors_allow_origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight responses for 1 hour
)

# Fallback preflight handler (ensures OPTIONS returns quickly and that middleware can attach headers)
@app.options("/{full_path:path}")
async def preflight(full_path: str, request: Request):
    origin = request.headers.get("origin")
    logger.debug(f"Fallback preflight handler invoked for path={full_path} origin={origin} headers={dict(request.headers)}")
    return Response(status_code=204)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Crimewatch Intel Backend",
        "version": "2.0.0",
        "status": "operational"
    }


@app.post("/api/refresh", response_model=RefreshResponse)
async def refresh_feed(
    request: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger ingestion for a specific region.
    
    Fetches new articles from all active sources in the region,
    enriches with Gemini Flash, and returns counts.
    """
    region = request.region
    logger.info(f"Refresh requested for region: {region}")
    
    # Sync the configured sources to DB when refresh is explicitly invoked
    try:
        synced_count = sync_sources_to_db(db, force_update=False)
        logger.info(f"Synced {synced_count} sources from configuration to database (on refresh)")
    except Exception as e:
        logger.warning(f"Failed to sync sources from config during refresh: {e}")
        logger.warning("Continuing refresh with existing database sources")
    
    # Find all active sources for this region
    sources = db.query(Source).filter(
        Source.region_label == region,
        Source.active == True
    ).all()
    
    if not sources:
        logger.warning(f"No active sources found for region: {region}")
        raise HTTPException(
            status_code=404,
            detail=f"No active sources found for region: {region}"
        )
    
    logger.info(f"Found {len(sources)} active sources for {region}")
    
    # Initialize enricher (will use dummy enrichment if GEMINI_API_KEY not set)
    enricher = None
    if os.getenv("DISABLE_ENRICHMENT", "").lower() in ("1", "true", "yes"):
        logger.info("Enrichment disabled via DISABLE_ENRICHMENT environment variable")
    else:
        try:
            enricher = GeminiEnricher()
            logger.info("Gemini enricher initialized")
        except ValueError as e:
            logger.warning(f"Gemini enrichment not available, using dummy enrichment: {e}")
    
    new_articles_count = 0
    
    # Process each source
    for source in sources:
        logger.info(f"Processing source: {source.agency_name}")
        
        # Get the most recent article date for this source
        latest_article = db.query(ArticleRaw).filter(
            ArticleRaw.source_id == source.id
        ).order_by(ArticleRaw.published_at.desc()).first()
        
        since = latest_article.published_at if latest_article else None
        logger.debug(f"Fetching articles since: {since}")
        
        # Get appropriate parser
        parser = get_parser(source.parser_id)

        # If parser supports per-source Playwright, set it from the source config
        if getattr(source, "use_playwright", False) and hasattr(parser, "use_playwright"):
            parser.use_playwright = True
        
        # Fetch new articles with timeout
        try:
            # Add timeout per source to prevent hanging
            new_articles = await asyncio.wait_for(
                parser.fetch_new_articles(
                    source_id=source.id,
                    base_url=source.base_url,
                    since=since
                ),
                timeout=SCRAPER_TIMEOUT_SECONDS
            )
            logger.info(f"Found {len(new_articles)} new articles from {source.agency_name}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching articles from {source.agency_name}")
            continue
        except Exception as e:
            logger.error(f"Failed to fetch articles from {source.agency_name}: {e}")
            continue

        # Upsert articles and enrich
        for article in new_articles:
            # Debug: log candidate article info
            logger.debug(f"Candidate article (source={source.agency_name}): url={article.url} external_id={article.external_id} title='{(article.title_raw or '')[:80]}' published_at={article.published_at}")

            # Skip non-HTTP URLs early to avoid noisy errors
            if not article.url or not (article.url.startswith("http://") or article.url.startswith("https://")):
                logger.debug(f"Skipping non-HTTP URL for article: {article.url}")
                continue

            # FILTER: Ensure URL looks like an article and is same-host as configured base_url
            is_valid = _is_valid_article_url(source, article.url)
            if not is_valid:
                logger.debug(f"Skipping URL not considered a valid article for source={source.agency_name}: {article.url} (base={source.base_url})")
                continue

            # Check if article already exists
            existing = db.query(ArticleRaw).filter(
                ArticleRaw.source_id == source.id,
                ArticleRaw.external_id == article.external_id
            ).first()

            if existing:
                logger.debug(f"Skipping duplicate article for source={source.agency_name} external_id={article.external_id} (existing id={existing.id})")
                continue  # Skip duplicates
            
            # Create new article
            db_article = ArticleRaw(
                source_id=source.id,
                external_id=article.external_id,
                url=article.url,
                title_raw=article.title_raw,
                published_at=article.published_at,
                body_raw=article.body_raw,
                raw_html=article.raw_html
            )
            db.add(db_article)
            db.flush()  # Get the ID
            
            # Enrich with Gemini or use dummy enrichment
            if enricher:
                try:
                    enrichment = await enricher.enrich_article(
                        title=article.title_raw,
                        body=article.body_raw,
                        agency=source.agency_name,
                        region=source.region_label,
                        published_at=article.published_at.isoformat() if article.published_at else None
                    )
                    llm_model = enricher.model_name
                    prompt_version = enricher.prompt_version
                except Exception as e:
                    logger.error(f"Enrichment failed for article {article.title_raw[:50]}: {e}")
                    # Fall back to dummy enrichment
                    summary_tactical = article.body_raw[:200] if len(article.body_raw) > 200 else article.body_raw
                    enrichment = {
                        "severity": "MEDIUM",
                        "summary_tactical": summary_tactical,
                        "tags": [],
                        "entities": [],
                        "location_label": None,
                        "lat": None,
                        "lng": None,
                        "graph_cluster_key": None
                    }
                    llm_model = "none"
                    prompt_version = "dummy_v1"
            else:
                # Dummy enrichment
                summary_tactical = article.body_raw[:200] if len(article.body_raw) > 200 else article.body_raw
                enrichment = {
                    "severity": "MEDIUM",
                    "summary_tactical": summary_tactical,
                    "tags": [],
                    "entities": [],
                    "location_label": None,
                    "lat": None,
                    "lng": None,
                    "graph_cluster_key": None
                }
                llm_model = "none"
                prompt_version = "dummy_v1"
            
            enriched = IncidentEnriched(
                id=db_article.id,
                severity=enrichment["severity"],
                summary_tactical=enrichment["summary_tactical"],
                tags=enrichment["tags"],
                entities=enrichment["entities"],
                location_label=enrichment.get("location_label"),
                lat=enrichment.get("lat"),
                lng=enrichment.get("lng"),
                graph_cluster_key=enrichment.get("graph_cluster_key"),
                llm_model=llm_model,
                prompt_version=prompt_version
            )
            db.add(enriched)
            new_articles_count += 1
            logger.debug(f"Enriched article: {article.title_raw[:50]}")
        
        # Update last_checked_at
        source.last_checked_at = datetime.now(timezone.utc)
        db.commit()
    
    # Count total incidents in this region
    total_incidents = db.query(IncidentEnriched).join(
        ArticleRaw, IncidentEnriched.id == ArticleRaw.id
    ).join(
        Source, ArticleRaw.source_id == Source.id
    ).filter(
        Source.region_label == region
    ).count()
    
    logger.info(f"Refresh complete: {new_articles_count} new articles, {total_incidents} total incidents for {region}")
    
    return RefreshResponse(
        region=region,
        new_articles=new_articles_count,
        total_incidents=total_incidents
    )


@app.get("/api/incidents", response_model=IncidentsResponse)
async def get_incidents(
    region: str = Query(..., description="Region label (e.g., 'Fraser Valley, BC')"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Get incidents for a specific region.
    
    Returns incidents in a format compatible with the frontend Incident type.
    """
    # Query incidents with joins
    incidents_data = db.query(
        ArticleRaw, IncidentEnriched, Source
    ).join(
        IncidentEnriched, ArticleRaw.id == IncidentEnriched.id
    ).join(
        Source, ArticleRaw.source_id == Source.id
    ).filter(
        Source.region_label == region
    ).order_by(
        ArticleRaw.published_at.desc()
    ).limit(limit).all()
    
    # Transform to response format
    incidents = []
    for article, enriched, source in incidents_data:
        # Map severity to match frontend enum
        severity_map = {
            "LOW": "Low",
            "MEDIUM": "Medium",
            "HIGH": "High",
            "CRITICAL": "Critical"
        }
        severity = severity_map.get(enriched.severity, "Medium")
        
        # Extract entities as strings
        entities_list = []
        if enriched.entities:
            for entity in enriched.entities:
                if isinstance(entity, dict):
                    entities_list.append(entity.get("name", str(entity)))
                else:
                    entities_list.append(str(entity))
        
        # Map source type
        source_type_map = {
            "RCMP_NEWSROOM": "Local Police",
            "MUNICIPAL_PD_NEWS": "Local Police",
            "STATE_POLICE": "State Police",
        }
        source_type = source_type_map.get(source.source_type, "Local Police")
        
        incident = IncidentResponse(
            id=str(article.id),
            timestamp=article.published_at.isoformat() if article.published_at else article.created_at.isoformat(),
            source=source_type,
            location=enriched.location_label or source.region_label,
            coordinates=CoordinatesSchema(
                lat=enriched.lat or 49.1042,  # Default to Fraser Valley area
                lng=enriched.lng or -122.6604
            ),
            summary=article.title_raw,
            fullText=article.body_raw,
            severity=severity,
            tags=enriched.tags or [],
            entities=entities_list,
            relatedIncidentIds=[]
        )
        incidents.append(incident)
    
    return IncidentsResponse(
        region=region,
        incidents=incidents
    )


# Add missing graph endpoint wrapper (previously an unterminated docstring)
@app.get("/api/graph", response_model=GraphResponse)
async def get_graph(
    region: str = Query(..., description="Region label (e.g., 'Fraser Valley, BC')"),
    db: Session = Depends(get_db)
):
    """
    Generate graph data for D3 network visualization.

    Returns nodes (incidents, entities, locations) and links.
    """
    # Query incidents for region
    incidents_data = db.query(
        ArticleRaw, IncidentEnriched, Source
    ).join(
        IncidentEnriched, ArticleRaw.id == IncidentEnriched.id
    ).join(
        Source, ArticleRaw.source_id == Source.id
    ).filter(
        Source.region_label == region
    ).all()
    
    nodes = []
    links = []
    entity_nodes = {}
    location_nodes = {}
    
    # Create incident nodes
    for article, enriched, source in incidents_data:
        incident_id = str(article.id)
        
        # Add incident node
        nodes.append(GraphNode(
            id=incident_id,
            label=enriched.summary_tactical[:50] + "..." if len(enriched.summary_tactical) > 50 else enriched.summary_tactical,
            type="incident",
            severity=enriched.severity
        ))
        
        # Process entities
        if enriched.entities:
            for entity in enriched.entities:
                if isinstance(entity, dict):
                    entity_type = entity.get("type", "person").lower()
                    entity_name = entity.get("name", "Unknown")
                    entity_id = f"{entity_type}_{entity_name.replace(' ', '_')}"
                    
                    if entity_id not in entity_nodes:
                        entity_nodes[entity_id] = GraphNode(
                            id=entity_id,
                            label=entity_name,
                            type=entity_type
                        )
                    
                    # Link incident to entity
                    links.append(GraphLink(
                        source=incident_id,
                        target=entity_id,
                        type="involved"
                    ))
        
        # Process location
        if enriched.location_label:
            location_id = f"loc_{enriched.location_label.replace(' ', '_').replace(',', '')}"
            
            if location_id not in location_nodes:
                location_nodes[location_id] = GraphNode(
                    id=location_id,
                    label=enriched.location_label,
                    type="location"
                )
            
            links.append(GraphLink(
                source=incident_id,
                target=location_id,
                type="occurred_at"
            ))
    
    # Add entity and location nodes
    nodes.extend(entity_nodes.values())
    nodes.extend(location_nodes.values())
    
    return GraphResponse(
        region=region,
        nodes=nodes,
        links=links
    )


@app.get("/api/map", response_model=MapResponse)
async def get_map(
    region: str = Query(..., description="Region label"),
    db: Session = Depends(get_db)
):
    """
    Get map markers for Leaflet visualization.
    """
    # Query incidents with coordinates
    incidents_data = db.query(
        ArticleRaw, IncidentEnriched, Source
    ).join(
        IncidentEnriched, ArticleRaw.id == IncidentEnriched.id
    ).join(
        Source, ArticleRaw.source_id == Source.id
    ).filter(
        Source.region_label == region,
        IncidentEnriched.lat.isnot(None),
        IncidentEnriched.lng.isnot(None)
    ).all()
    
    markers = []
    for article, enriched, source in incidents_data:
        severity_map = {
            "LOW": "Low",
            "MEDIUM": "Medium",
            "HIGH": "High",
            "CRITICAL": "Critical"
        }
        
        markers.append(MapMarker(
            incidentId=str(article.id),
            lat=enriched.lat,
            lng=enriched.lng,
            severity=severity_map.get(enriched.severity, "Medium"),
            label=enriched.summary_tactical
        ))
    
    return MapResponse(
        region=region,
        markers=markers
    )


@app.get("/api/debug/candidates")
async def debug_candidates(
    source_id: Optional[int] = Query(None),
    base_url: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    DEV-only endpoint: return anchor candidate diagnostics for a source listing.
    Pass either source_id or base_url. Disabled unless ENV == 'dev'.
    """
    if ENV != "dev":
        raise HTTPException(status_code=403, detail="Debug endpoint only available in dev environment")

    if not source_id and not base_url:
        raise HTTPException(status_code=400, detail="Provide source_id or base_url")

    if source_id:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        target_url = source.base_url
        parser_id = source.parser_id
    else:
        target_url = base_url
        # attempt to infer parser id from sources config DB if available
        src = db.query(Source).filter(Source.base_url == base_url).first()
        parser_id = src.parser_id if src else "rcmp"

    parser = get_parser(parser_id)
    # If parser has the diagnostics method, call it
    if hasattr(parser, "discover_candidate_anchors"):
        try:
            diagnostics = await parser.discover_candidate_anchors(target_url)
            return JSONResponse({"base_url": target_url, "diagnostics": diagnostics})
        except Exception as e:
            logger.exception("Debug candidate discovery failed")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Parser does not support candidate discovery")


@app.get("/api/debug/render", response_class=HTMLResponse)
async def debug_render(
    source_id: Optional[int] = Query(None),
    base_url: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    DEV-only endpoint: return the rendered HTML for a source listing.
    Use it to inspect the final rendered HTML (Playwright) or server-side HTML,
    to verify anchors are present. Disabled unless ENV == 'dev'.
    """
    if ENV != "dev":
        raise HTTPException(status_code=403, detail="Debug endpoint only available in dev environment")

    if not source_id and not base_url:
        raise HTTPException(status_code=400, detail="Provide source_id or base_url")

    if source_id:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        target_url = source.base_url
        parser_id = source.parser_id
    else:
        target_url = base_url
        src = db.query(Source).filter(Source.base_url == base_url).first()
        parser_id = src.parser_id if src else "rcmp"

    parser = get_parser(parser_id)
    # If parser has the render helper, call it
    if hasattr(parser, "render_listing_page"):
        try:
            rendered_html = await parser.render_listing_page(target_url)
            if not rendered_html:
                raise HTTPException(status_code=500, detail="Failed to fetch/render listing page")
            return HTMLResponse(content=rendered_html)
        except Exception as e:
            logger.exception("Debug render failed")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Parser does not support rendering")


def get_parser(parser_id: str):
    """
    Factory function to get the appropriate parser based on parser_id.
    """
    if parser_id == "rcmp":
        # Use Playwright-based RCMP parser
        return RCMPParser(use_playwright=True, allow_test_json=False)
    elif parser_id == "wordpress":
        return WordPressParser()
    elif parser_id == "municipal_list":
        return MunicipalListParser()
    else:
        raise ValueError(f"Unknown parser_id: {parser_id}")


def _is_valid_article_url(source, article_url: str) -> bool:
    """
    Heuristic to validate that an extracted URL is actually an article we want to index.
    - Must be a http/https URL.
    - Must be the same netloc as the source base_url. Use endswith comparison to allow www vs non-www.
    - Must not be the same path as the listing base_url (avoid listing pages and anchors).
    - For RCMP sources, require '/news/' and digits (year/id) somewhere in the path.
    - Avoid obvious non-article content paths (about, contact, cookie, privacy, terms).
    """
    if not article_url:
        return False

    try:
        parsed = urlparse(article_url)
        if parsed.scheme not in ("http", "https"):
            return False
    except Exception:
        return False

    base_parsed = urlparse(source.base_url)
    # Ensure same host so we don't capture external links — allow www variations
    if parsed.netloc and not parsed.netloc.lower().endswith(base_parsed.netloc.lower()):
        logger.debug(f"_is_valid_article_url: host mismatch parsed={parsed.netloc} base={base_parsed.netloc}")
        return False

    # Avoid base listing URL (with or without trailing slash or fragment)
    base_path = base_parsed.path.rstrip('/')
    if parsed.path.rstrip('/') == base_path:
        logger.debug(f"_is_valid_article_url: path equals base listing path: {parsed.path}")
        return False

    path_lower = parsed.path.lower()

    # Skip obvious non-article pages
    non_article_prefixes = ["/about", "/contact", "/cookie", "/cookies", "/privacy", "/terms", "/careers", "/join-us"]
    for prefix in non_article_prefixes:
        if path_lower.startswith(prefix):
            logger.debug(f"_is_valid_article_url: path has non-article prefix: {prefix} -> {path_lower}")
            return False

    # Specific RCMP heuristics: articles live under '/news/' with a numeric resource id or node id
    if getattr(source, "parser_id", "") == "rcmp":
        if "/news/" not in path_lower and not re.search(r"/node/\d+", path_lower):
            logger.debug(f"_is_valid_article_url: RCMP link missing /news/ or /node/ : {path_lower}")
            return False
        # accept /news/*digits* or node id patterns
        if not re.search(r"/news/.*/\d+|/news/.*\d|/node/\d+", path_lower):
            logger.debug(f"_is_valid_article_url: RCMP link does not match news/node numeric pattern: {path_lower}")
            return False

    # All checks passed — consider valid
    return True


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))