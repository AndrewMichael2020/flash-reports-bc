import { SimulationNodeDatum, SimulationLinkDatum } from 'd3';

export enum Severity {
  LOW = 'Low',
  MEDIUM = 'Medium',
  HIGH = 'High',
  CRITICAL = 'Critical'
}

export enum SourceType {
  POLICE_LOCAL = 'Local Police',
  POLICE_STATE = 'State Police',
  PENITENTIARY = 'Penitentiary',
  PORT_AUTHORITY = 'Port Authority',
  HIGHWAY_PATROL = 'Highway Patrol',
  SPECIALIZED = 'Specialized Unit'
}

export interface Incident {
  id: string;
  timestamp: string;
  // Optional: when the incident actually occurred, if backend knows it
  incidentOccurredAt?: string | null;
  source: SourceType;
  location: string;
  coordinates: { lat: number; lng: number };
  summary: string;
  fullText: string;
  severity: Severity;
  tags: string[];
  entities: string[];
  relatedIncidentIds: string[];
  // Link back to original newsroom article (to be mapped from backend later)
  sourceUrl?: string;
  // Enriched citizen-facing fields
  crimeCategory?: string | null;
  temporalContext?: string | null;
  weaponInvolved?: string | null;
  tacticalAdvice?: string | null;
}

export interface GraphNode extends SimulationNodeDatum {
  id: string;
  label: string;
  type: 'root' | 'incident' | 'location' | 'group' | 'person' | 'tag'; // Added root and tag
  severity?: Severity;
  level?: number; // For tree layout depth
  // D3 Simulation properties
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  vx?: number;
  vy?: number;
  index?: number;
}

export interface GraphLink extends SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
  type: 'occurred_at' | 'involved' | 'related_to';
}

export interface NetworkData {
  nodes: GraphNode[];
  links: GraphLink[];
}