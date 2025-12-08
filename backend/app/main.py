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
import uuid
from urllib.parse import urlparse
from fastapi import FastAPI, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone
from starlette.responses import Response
from fastapi.responses import JSONResponse, HTMLResponse

from app.db import get_db, engine, Base
from app.models import Source, ArticleRaw, IncidentEnriched, RefreshJob
from app.schemas import (
    RefreshRequest, RefreshResponse,
    RefreshAsyncRequest, RefreshAsyncResponse, RefreshStatusResponse,
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
from sqlalchemy import inspect

def verify_database_schema():
    """
    Verify that the database schema is up-to-date.
    Checks for required columns that were added in recent migrations.
    
    Returns:
        tuple: (is_valid: bool, message: str)
            - is_valid: True if schema is valid, False otherwise
            - message: Description of validation result or error
    """
    inspector = inspect(engine)
    
    # Check if incidents_enriched table exists
    if 'incidents_enriched' not in inspector.get_table_names():
        return False, "Table 'incidents_enriched' does not exist. Run 'alembic upgrade head' to create tables."
    
    # Check for required columns (added in various migrations)
    # These columns are essential for the current version of the application
    required_columns = ['crime_category', 'temporal_context', 'weapon_involved', 'tactical_advice']
    existing_columns = [col['name'] for col in inspector.get_columns('incidents_enriched')]
    
    missing_columns = [col for col in required_columns if col not in existing_columns]
    
    if missing_columns:
        return False, f"Missing columns in incidents_enriched table: {', '.join(missing_columns)}. Run 'alembic upgrade head' to update schema."
    
    return True, "Database schema is up-to-date"

# Configuration constants
SCRAPER_TIMEOUT_SECONDS = 45.0  # Timeout per source when fetching articles (was 30.0)

# Default enrichment values for fallback when LLM enrichment fails or is unavailable
DEFAULT_ENRICHMENT_VALUES = {
    "severity": "MEDIUM",
    "tags": [],
    "entities": [],
    "location_label": None,
    "lat": None,
    "lng": None,
    "graph_cluster_key": None,
    "crime_category": "Unknown",
    "temporal_context": None,
    "weapon_involved": None,
    "tactical_advice": None,
}

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
    
    # Verify database schema is up-to-date
    schema_valid, schema_message = verify_database_schema()
    if not schema_valid:
        logger.error(f"Database schema verification failed: {schema_message}")
        logger.error("Please run 'alembic upgrade head' to update the database schema.")
        raise RuntimeError(f"Database schema is outdated: {schema_message}")
    logger.info(f"Database schema verification: {schema_message}")
    
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


async def perform_refresh_for_region(region: str, db: Session) -> RefreshResponse:
    """
    Core refresh logic extracted for reuse by both sync and async endpoints.
    
    Fetches new articles from all active sources in the region,
    enriches with Gemini Flash, and returns counts.
    
    Args:
        region: Region label to refresh
        db: Database session
        
    Returns:
        RefreshResponse with new_articles and total_incidents counts
        
    Raises:
        HTTPException: If no active sources found for region
    """
    logger.info(f"Performing refresh for region: {region}")
    
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
    # Log the list of sources actually being processed for this refresh
    logger.debug(
        "Active sources for region %s: %s",
        region,
        [f"{s.id}:{s.agency_name} parser={s.parser_id} base_url={s.base_url}" for s in sources],
    )

    # Initialize enricher (will use dummy enrichment if GEMINI_API_KEY not set)
    enricher = None
    if os.getenv("DISABLE_ENRICHMENT", "").lower() in ("1", "true", "yes"):
        logger.info("Enrichment disabled via DISABLE_ENRICHMENT environment variable")
    else:
        try:
            enricher = GeminiEnricher()
            logger.info(f"Gemini enricher initialized with model={enricher.model_name} prompt_version={enricher.prompt_version}")
        except ValueError as e:
            # This is the "no GEMINI_API_KEY" case
            logger.warning(f"Gemini enrichment not available, using dummy enrichment: {e}")
        except Exception as e:
            # Any other init failure
            logger.error(f"Gemini enricher initialization failed, using dummy enrichment: {e}", exc_info=True)

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
            logger.debug(
                f"Candidate article (source={source.agency_name}): "
                f"url={article.url} external_id={article.external_id} "
                f"title='{(article.title_raw or '')[:80]}' published_at={article.published_at}"
            )

            # Skip non-HTTP URLs early to avoid noisy errors
            if not article.url or not (article.url.startswith("http://") or article.url.startswith("https://")):
                logger.debug(f"Skipping non-HTTP URL for article: {article.url}")
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
                    logger.debug(f"Calling GeminiEnricher for article id={db_article.id} title='{article.title_raw[:80]}'")
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
                    logger.error(f"Enrichment failed for article id={db_article.id} title='{article.title_raw[:80]}': {e}")
                    # Fall back to dummy enrichment
                    summary_tactical = article.body_raw[:200] if len(article.body_raw) > 200 else article.body_raw
                    enrichment = {
                        **DEFAULT_ENRICHMENT_VALUES,
                        "summary_tactical": summary_tactical,
                        "incident_occurred_at": None,
                    }
                    llm_model = "none"
                    prompt_version = "dummy_v1"
            else:
                logger.debug(f"Enricher is None, using dummy enrichment for article id={db_article.id}")
                summary_tactical = article.body_raw[:200] if len(article.body_raw) > 200 else article.body_raw
                enrichment = {
                    **DEFAULT_ENRICHMENT_VALUES,
                    "summary_tactical": summary_tactical,
                    "incident_occurred_at": None,
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
                crime_category=enrichment.get("crime_category", "Unknown"),
                temporal_context=enrichment.get("temporal_context"),
                weapon_involved=enrichment.get("weapon_involved"),
                tactical_advice=enrichment.get("tactical_advice"),
                llm_model=llm_model,
                prompt_version=prompt_version,
                # Use LLM-derived incident time if available
                incident_occurred_at=enrichment.get("incident_occurred_at"),
            )
            db.add(enriched)
            new_articles_count += 1
            logger.debug(f"Enriched article id={db_article.id} llm_model={llm_model} prompt_version={prompt_version}")
        
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


@app.post("/api/refresh", response_model=RefreshResponse)
async def refresh_feed(
    request: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Synchronous refresh endpoint for a specific region.
    
    Fetches new articles from all active sources in the region,
    enriches with Gemini Flash, and returns counts.
    
    Note: This endpoint may timeout for long-running refreshes.
    Consider using /api/refresh-async for better reliability.
    """
    return await perform_refresh_for_region(request.region, db)


async def background_refresh_task(job_id: str, region: str):
    """
    Background task to perform refresh asynchronously.
    Updates job status in database as it progresses.
    
    Args:
        job_id: UUID of the refresh job
        region: Region to refresh
    """
    db = next(get_db())
    try:
        # Update job status to running
        job = db.query(RefreshJob).filter(RefreshJob.job_id == job_id).first()
        if not job:
            logger.error(f"Background refresh task: Job {job_id} not found")
            return
        
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Background refresh started for job {job_id}, region {region}")
        
        # Perform the actual refresh
        try:
            result = await perform_refresh_for_region(region, db)
            
            # Update job as succeeded
            job.status = "succeeded"
            job.new_articles = result.new_articles
            job.total_incidents = result.total_incidents
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Background refresh succeeded for job {job_id}: {result.new_articles} new articles")
            
        except HTTPException as e:
            # Handle known exceptions (like no sources found)
            job.status = "failed"
            job.error_message = str(e.detail)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.error(f"Background refresh failed for job {job_id}: {e.detail}")
            
        except Exception as e:
            # Handle unexpected errors
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.error(f"Background refresh failed for job {job_id}: {e}", exc_info=True)
            
    finally:
        db.close()


@app.post("/api/refresh-async", response_model=RefreshAsyncResponse)
async def refresh_feed_async(
    request: RefreshAsyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger asynchronous refresh for a specific region.
    
    Returns immediately with a job ID that can be used to poll status.
    The actual refresh happens in the background.
    
    Args:
        request: Request containing region to refresh
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        RefreshAsyncResponse with job_id for status polling
    """
    region = request.region
    job_id = str(uuid.uuid4())
    
    logger.info(f"Async refresh requested for region: {region}, job_id: {job_id}")
    
    # Create job record
    job = RefreshJob(
        job_id=job_id,
        region=region,
        status="pending",
        created_at=datetime.now(timezone.utc)
    )
    db.add(job)
    db.commit()
    
    # Schedule background task
    background_tasks.add_task(background_refresh_task, job_id, region)
    
    logger.info(f"Created async refresh job {job_id} for region {region}")
    
    return RefreshAsyncResponse(
        job_id=job_id,
        region=region,
        status="pending",
        message=f"Refresh job started for {region}. Poll /api/refresh-status/{job_id} for status."
    )


@app.get("/api/refresh-status/{job_id}", response_model=RefreshStatusResponse)
async def get_refresh_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get status of an asynchronous refresh job.
    
    Args:
        job_id: UUID of the refresh job
        db: Database session
        
    Returns:
        RefreshStatusResponse with current job status and results
        
    Raises:
        HTTPException: If job not found
    """
    job = db.query(RefreshJob).filter(RefreshJob.job_id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Refresh job {job_id} not found"
        )
    
    return RefreshStatusResponse(
        job_id=job.job_id,
        region=job.region,
        status=job.status,
        new_articles=job.new_articles,
        total_incidents=job.total_incidents,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None
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
    # Order by "effective" time: incident_occurred_at (if set), else published_at, else created_at.
    incidents_data = db.query(
        ArticleRaw, IncidentEnriched, Source
    ).join(
        IncidentEnriched, ArticleRaw.id == IncidentEnriched.id
    ).join(
        Source, ArticleRaw.source_id == Source.id
    ).filter(
        Source.region_label == region
    ).order_by(
        # Newest effective time on top
        (IncidentEnriched.incident_occurred_at
         .desc()
         .nullslast()),
        (ArticleRaw.published_at
         .desc()
         .nullslast()),
        ArticleRaw.created_at.desc(),
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

        # Effective timestamp for UI feed: event time if known, else publication, else created_at
        if enriched.incident_occurred_at:
            effective_ts = enriched.incident_occurred_at
        elif article.published_at:
            effective_ts = article.published_at
        else:
            effective_ts = article.created_at

        incident = IncidentResponse(
            id=str(article.id),
            timestamp=effective_ts.isoformat(),
            source=source_type,
            location=enriched.location_label or source.region_label,
            coordinates=CoordinatesSchema(
                lat=enriched.lat or 49.1042,
                lng=enriched.lng or -122.6604
            ),
            summary=article.title_raw,
            fullText=article.body_raw,
            severity=severity,
            tags=enriched.tags or [],
            entities=entities_list,
            relatedIncidentIds=[],
            crimeCategory=enriched.crime_category,
            temporalContext=enriched.temporal_context,
            weaponInvolved=enriched.weapon_involved,
            tacticalAdvice=enriched.tactical_advice,
            incidentOccurredAt=enriched.incident_occurred_at.isoformat() if enriched.incident_occurred_at else None,
            agencyName=source.agency_name,
        )
        incidents.append(incident)

    return IncidentsResponse(
        region=region,
        incidents=incidents,
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


@app.get("/api/debug/enrichment-check")
async def debug_enrichment_check():
    """
    DEV-only endpoint: validate enrichment configuration and perform a test enrichment.
    Returns status of enricher initialization and test enrichment attempt.
    """
    if ENV != "dev":
        raise HTTPException(status_code=403, detail="Debug endpoint only available in dev environment")
    
    result = {
        "ok": False,
        "error": None,
        "model_name": None,
        "prompt_version": None,
        "api_key_present": bool(os.getenv("GEMINI_API_KEY")),
        "test_enrichment": None
    }
    
    try:
        # Try to initialize enricher
        enricher = GeminiEnricher()
        result["model_name"] = enricher.model_name
        result["prompt_version"] = enricher.prompt_version
        
        # Try a minimal test enrichment
        test_article = {
            "title": "Test Article - Vehicle Collision Investigation",
            "body": "Police are investigating a two-vehicle collision that occurred on Highway 1 near 264th Street. No injuries reported.",
            "agency": "Test Agency",
            "region": "Test Region"
        }
        
        enrichment = await enricher.enrich_article(**test_article)
        result["test_enrichment"] = {
            "severity": enrichment.get("severity"),
            "has_summary": bool(enrichment.get("summary_tactical")),
            "tags_count": len(enrichment.get("tags", [])),
            "entities_count": len(enrichment.get("entities", []))
        }
        result["ok"] = True
        
    except ValueError as e:
        # Missing API key or config issue
        result["error"] = str(e)
        logger.warning(f"Enrichment check failed: {e}")
    except Exception as e:
        # Any other error
        result["error"] = f"Unexpected error: {str(e)}"
        logger.error(f"Enrichment check failed with unexpected error: {e}")
    
    return JSONResponse(result)


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
        target_url = base_url
        # attempt to infer parser id from sources config DB if available
        src = db.query(Source).filter(Source.base_url == base_url).first()
        parser_id = src.parser_id if src else None

    # For dev, always allow http://localhost links
    if target_url and "localhost" in target_url:
        logger.info(f"Allowing localhost target URL for dev candidate debug: {target_url}")
    else:
        # In production, enforce valid URL structure
        parsed = urlparse(target_url)
        if not (parsed.scheme and parsed.netloc):
            raise HTTPException(status_code=400, detail="Invalid URL structure for base_url")

    # Lookup parser by ID
    parser = get_parser(parser_id)

    # For dev, allow overriding parser via query param (for testing different parsers)
    if ENV == "dev" and parser_id != "rcmp" and parser_id != "municipal_list" and parser_id != "wordpress":
        logger.warning(f"DEV overriding parser to 'rcmp' for source_id={source_id} base_url={base_url}")
        parser_id = "rcmp"
        parser = get_parser(parser_id)

    logger.info(f"Debug candidates for source_id={source_id} base_url={base_url} using parser_id={parser_id}")

    # For dev, relax URL validation to allow any http(s) URL
    def relaxed_url_validator(url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")

    # Legacy URL heuristic (no longer used in ingestion).
    # Parsers (RCMP, municipal_list, wordpress) are now responsible for filtering
    # which links are treated as articles.
    def _is_valid_article_url(source, article_url: str) -> bool:
        return True

    # Get anchor candidates
    try:
        candidates = await parser.get_anchor_candidates(
            base_url=target_url,
            source_id=source_id,
            url_validator=relaxed_url_validator
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching candidates: {e}")
    
    logger.info(f"Found {len(candidates)} anchor candidates for {target_url}")
    
    return {
        "source_id": source_id,
        "base_url": target_url,
        "parser_id": parser_id,
        "candidates": candidates
    }


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
        # Add explicit logging to help debug DB/config issues
        logger.error("Unknown parser_id in Source configuration: %s", parser_id)
        raise ValueError(f"Unknown parser_id: {parser_id}")