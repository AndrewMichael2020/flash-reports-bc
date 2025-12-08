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
    # New citizen-facing fields (optional to avoid breaking existing clients)
    crimeCategory: Optional[str] = None
    temporalContext: Optional[str] = None
    weaponInvolved: Optional[str] = None
    tacticalAdvice: Optional[str] = None
    # New optional field: ISO timestamp when the incident occurred (if known)
    incidentOccurredAt: Optional[str] = None
    # New: specific agency/department name (e.g. "Langley RCMP")
    agencyName: Optional[str] = None


class IncidentsResponse(BaseModel):
    """Response from GET /api/incidents."""
    region: str
    incidents: List[IncidentResponse]


class GraphNode(BaseModel):
    """Node in the network graph."""
    id: str
    label: str
    type: str  # "incident" | "person" | "group" | "location"
    severity: Optional[str] = None


class GraphLink(BaseModel):
    """Link between nodes in the graph."""
    source: str
    target: str
    type: str  # "involved" | "occurred_at" | "related_to"


class GraphResponse(BaseModel):
    """Response from GET /api/graph."""
    region: str
    nodes: List[GraphNode]
    links: List[GraphLink]


class MapMarker(BaseModel):
    """Map marker for a single incident."""
    incidentId: str
    lat: float
    lng: float
    severity: str
    label: str


class MapResponse(BaseModel):
    """Response from GET /api/map."""
    region: str
    markers: List[MapMarker]


class RefreshAsyncRequest(BaseModel):
    """Request to trigger async refresh for a region."""
    region: str


class RefreshAsyncResponse(BaseModel):
    """Response from POST /api/refresh-async."""
    job_id: str
    region: str
    status: str
    message: str


class RefreshStatusResponse(BaseModel):
    """Response from GET /api/refresh-status/{job_id}."""
    job_id: str
    region: str
    status: str  # 'pending' | 'running' | 'succeeded' | 'failed'
    new_articles: Optional[int] = None
    total_incidents: Optional[int] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
