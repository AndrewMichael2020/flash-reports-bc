"""
Pydantic schemas for request/response validation.
These schemas match the TypeScript types in the frontend.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RefreshRequest(BaseModel):
    """Request to refresh feed for a region."""
    region: str


class RefreshResponse(BaseModel):
    """Response from refresh endpoint."""
    region: str
    new_articles: int
    total_incidents: int


class EntitySchema(BaseModel):
    """Entity extracted from an incident (matching TS interface)."""
    type: str
    name: str


class CoordinatesSchema(BaseModel):
    """Geographic coordinates."""
    lat: float
    lng: float


class IncidentResponse(BaseModel):
    """
    Incident schema matching the TypeScript Incident type in types.ts.
    Note: The frontend expects 'entities' as string[], but we store as objects.
    We'll transform in the endpoint.
    """
    id: str
    timestamp: str
    source: str  # Will map from SourceType enum
    location: str
    coordinates: CoordinatesSchema
    summary: str
    fullText: str
    severity: str  # "Low" | "Medium" | "High" | "Critical"
    tags: List[str]
    entities: List[str]  # Frontend expects string array
    relatedIncidentIds: List[str]


class IncidentsResponse(BaseModel):
    """Response from GET /api/incidents."""
    region: str
    incidents: List[IncidentResponse]
