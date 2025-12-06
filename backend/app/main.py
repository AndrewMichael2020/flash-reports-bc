"""
FastAPI application main entry point.
Implements endpoints for the Crimewatch Intel backend.
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import os

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

from contextlib import asynccontextmanager

# Create tables on startup (for development)
# In production, use Alembic migrations
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown."""
    # Startup: seed database with BC sources
    db = next(get_db())
    
    # Check if we have any sources
    existing_sources = db.query(Source).count()
    
    if existing_sources == 0:
        # Seed with BC sources
        sources_to_add = [
            # RCMP Detachments (using new rcmp.ca URL structure)
            Source(
                agency_name="Langley RCMP",
                jurisdiction="BC",
                region_label="Fraser Valley, BC",
                source_type="RCMP_NEWSROOM",
                base_url="https://rcmp.ca/en/bc/langley/news",
                parser_id="rcmp",
                active=True
            ),
            Source(
                agency_name="Chilliwack RCMP",
                jurisdiction="BC",
                region_label="Fraser Valley, BC",
                source_type="RCMP_NEWSROOM",
                base_url="https://rcmp.ca/en/bc/chilliwack/news",
                parser_id="rcmp",
                active=True
            ),
            Source(
                agency_name="Mission RCMP",
                jurisdiction="BC",
                region_label="Fraser Valley, BC",
                source_type="RCMP_NEWSROOM",
                base_url="https://rcmp.ca/en/bc/mission/news",
                parser_id="rcmp",
                active=True
            ),
            # Municipal Police
            Source(
                agency_name="Surrey Police Service",
                jurisdiction="BC",
                region_label="Fraser Valley, BC",
                source_type="MUNICIPAL_PD_NEWS",
                base_url="https://www.surreypolice.ca/news-releases",
                parser_id="municipal_list",
                active=True
            ),
            Source(
                agency_name="Abbotsford Police Department",
                jurisdiction="BC",
                region_label="Fraser Valley, BC",
                source_type="MUNICIPAL_PD_NEWS",
                base_url="https://www.abbypd.ca/news-releases",
                parser_id="municipal_list",
                active=True
            ),
            Source(
                agency_name="Vancouver Police Department",
                jurisdiction="BC",
                region_label="Metro Vancouver, BC",
                source_type="MUNICIPAL_PD_NEWS",
                base_url="https://vpd.ca/news/",
                parser_id="wordpress",
                active=True
            ),
            Source(
                agency_name="Victoria Police Department",
                jurisdiction="BC",
                region_label="Victoria, BC",
                source_type="MUNICIPAL_PD_NEWS",
                base_url="https://vicpd.ca/about-us/news-releases-dashboard/",
                parser_id="municipal_list",
                active=True
            ),
        ]
        
        for source in sources_to_add:
            db.add(source)
        
        db.commit()
        print(f"✓ Seeded database with {len(sources_to_add)} BC sources")
    
    db.close()
    
    yield
    
    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="Crimewatch Intel Backend",
    description="Backend API for Crimewatch Intel police newsroom aggregator",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware to allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    
    # Find all active sources for this region
    sources = db.query(Source).filter(
        Source.region_label == region,
        Source.active == True
    ).all()
    
    if not sources:
        raise HTTPException(
            status_code=404,
            detail=f"No active sources found for region: {region}"
        )
    
    # Initialize enricher (will use dummy enrichment if GEMINI_API_KEY not set)
    enricher = None
    try:
        enricher = GeminiEnricher()
    except ValueError as e:
        print(f"Warning: Gemini enrichment not available, using dummy enrichment: {e}")
    
    new_articles_count = 0
    
    # Process each source
    for source in sources:
        # Get the most recent article date for this source
        latest_article = db.query(ArticleRaw).filter(
            ArticleRaw.source_id == source.id
        ).order_by(ArticleRaw.published_at.desc()).first()
        
        since = latest_article.published_at if latest_article else None
        
        # Get appropriate parser
        parser = get_parser(source.parser_id)
        
        # Fetch new articles
        new_articles = await parser.fetch_new_articles(
            source_id=source.id,
            base_url=source.base_url,
            since=since
        )
        
        # Upsert articles and enrich
        for article in new_articles:
            # Check if article already exists
            existing = db.query(ArticleRaw).filter(
                ArticleRaw.source_id == source.id,
                ArticleRaw.external_id == article.external_id
            ).first()
            
            if existing:
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
                enrichment = await enricher.enrich_article(
                    title=article.title_raw,
                    body=article.body_raw,
                    agency=source.agency_name,
                    region=source.region_label,
                    published_at=article.published_at.isoformat() if article.published_at else None
                )
                llm_model = enricher.model_name
                prompt_version = enricher.prompt_version
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
        
        # Update last_checked_at
        source.last_checked_at = datetime.utcnow()
        db.commit()
    
    # Count total incidents in this region
    total_incidents = db.query(IncidentEnriched).join(
        ArticleRaw, IncidentEnriched.id == ArticleRaw.id
    ).join(
        Source, ArticleRaw.source_id == Source.id
    ).filter(
        Source.region_label == region
    ).count()
    
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


@app.get("/api/graph", response_model=GraphResponse)
async def get_graph(
    region: str = Query(..., description="Region label"),
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


def get_parser(parser_id: str):
    """
    Factory function to get the appropriate parser based on parser_id.
    """
    parsers = {
        "rcmp": RCMPParser(),
        "wordpress": WordPressParser(),
        "municipal_list": MunicipalListParser(),
    }
    
    parser = parsers.get(parser_id)
    if not parser:
        raise ValueError(f"Unknown parser_id: {parser_id}")
    
    return parser


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
