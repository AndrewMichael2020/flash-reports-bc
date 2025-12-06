"""
FastAPI application main entry point.
Implements endpoints for the Crimewatch Intel backend.
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.db import get_db, engine, Base
from app.models import Source, ArticleRaw, IncidentEnriched
from app.schemas import (
    RefreshRequest, RefreshResponse,
    IncidentsResponse, IncidentResponse,
    CoordinatesSchema
)
from app.ingestion.rcmp_parser import RCMPParser

from contextlib import asynccontextmanager

# Create tables on startup (for development)
# In production, use Alembic migrations
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown."""
    # Startup: seed database
    db = next(get_db())
    
    # Check if we have any sources
    existing_sources = db.query(Source).count()
    
    if existing_sources == 0:
        # Seed with one RCMP source for Fraser Valley, BC
        langley_rcmp = Source(
            agency_name="Langley RCMP",
            jurisdiction="BC",
            region_label="Fraser Valley, BC",
            source_type="RCMP_NEWSROOM",
            base_url="https://bc-cb.rcmp-grc.gc.ca/ViewPage.action?siteNodeId=2087&languageId=1&contentId=-1",
            parser_id="rcmp",
            active=True
        )
        db.add(langley_rcmp)
        db.commit()
        print("✓ Seeded database with Langley RCMP source")
    
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
    creates dummy enriched incidents, and returns counts.
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
        
        # Upsert articles and create dummy enrichment
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
            
            # Create dummy enrichment
            summary_tactical = article.body_raw[:200] if len(article.body_raw) > 200 else article.body_raw
            
            enriched = IncidentEnriched(
                id=db_article.id,
                severity="MEDIUM",
                summary_tactical=summary_tactical,
                tags=[],
                entities=[],
                location_label=None,
                lat=None,
                lng=None,
                graph_cluster_key=None,
                llm_model="none",
                prompt_version="dummy_v1"
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


def get_parser(parser_id: str):
    """
    Factory function to get the appropriate parser based on parser_id.
    """
    parsers = {
        "rcmp": RCMPParser(),
    }
    
    parser = parsers.get(parser_id)
    if not parser:
        raise ValueError(f"Unknown parser_id: {parser_id}")
    
    return parser


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
