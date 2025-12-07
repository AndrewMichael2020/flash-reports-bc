"""
SQLAlchemy ORM models for the database schema.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
from app.db import Base
import os

# Use JSONB for PostgreSQL, JSON for SQLite
JsonType = JSONB if not os.getenv("DATABASE_URL", "sqlite").startswith("sqlite") else JSON


class Source(Base):
    """
    Static registry of police newsroom endpoints.
    """
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, index=True)
    agency_name = Column(Text, nullable=False)
    jurisdiction = Column(Text, nullable=False)  # e.g., 'BC', 'AB', 'WA'
    region_label = Column(Text, nullable=False)  # e.g., 'Fraser Valley, BC'
    source_type = Column(Text, nullable=False)   # e.g., 'RCMP_NEWSROOM'
    base_url = Column(Text, nullable=False)
    parser_id = Column(Text, nullable=False)     # which parser to use
    active = Column(Boolean, nullable=False, default=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    use_playwright = Column(Boolean, nullable=False, default=False)


class ArticleRaw(Base):
    """
    Raw articles scraped from newsroom pages.
    """
    __tablename__ = "articles_raw"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    external_id = Column(Text, nullable=False)   # hash of URL+title for idempotence
    url = Column(Text, nullable=False)
    title_raw = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    body_raw = Column(Text, nullable=False)
    raw_html = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('source_id', 'external_id', name='uq_source_external'),
    )


class IncidentEnriched(Base):
    """
    Enriched incidents with LLM-extracted intelligence.
    1:1 relationship with articles_raw.
    """
    __tablename__ = "incidents_enriched"
    
    id = Column(Integer, ForeignKey("articles_raw.id", ondelete="CASCADE"), primary_key=True)
    severity = Column(Text, nullable=False)  # 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
    summary_tactical = Column(Text, nullable=False)
    tags = Column(JsonType, nullable=False)         # array of strings
    entities = Column(JsonType, nullable=False)     # [{ "type": "Person", "name": "..." }, ...]
    location_label = Column(Text, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    graph_cluster_key = Column(Text, nullable=True)
    llm_model = Column(Text, nullable=False)
    prompt_version = Column(Text, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
