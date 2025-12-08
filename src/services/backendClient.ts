/**
 * Backend API client for Crimewatch Intel.
 * Provides functions to interact with the FastAPI backend.
 * 
 * In DEV mode (default), uses same-origin relative paths (e.g., "/api/refresh")
 * which Vite proxies to backend. In production, set VITE_API_BASE_URL to the
 * actual backend URL.
 */

// Default to "/" for same-origin requests (DEV mode with Vite proxy)
// In production, set VITE_API_BASE_URL to full backend URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/';

/**
 * Normalize API base URL to ensure proper path construction.
 * Removes trailing slash for consistent path joining.
 */
function normalizeBaseUrl(base: string): string {
  return base.endsWith('/') ? base.slice(0, -1) : base;
}

export interface RefreshResponse {
  region: string;
  new_articles: number;
  total_incidents: number;
}

export interface IncidentsResponse {
  region: string;
  incidents: any[];
}

export interface GraphResponse {
  region: string;
  nodes: any[];
  links: any[];
}

export interface MapResponse {
  region: string;
  markers: any[];
}

export interface RefreshAsyncResponse {
  job_id: string;
  region: string;
  status: string;
  message: string;
}

export interface RefreshStatusResponse {
  job_id: string;
  region: string;
  status: string; // 'pending' | 'running' | 'succeeded' | 'failed'
  new_articles: number | null;
  total_incidents: number | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Trigger feed refresh for a specific region.
 * Calls POST /api/refresh on the backend.
 */
export async function refreshFeed(region: string): Promise<RefreshResponse> {
  const baseUrl = normalizeBaseUrl(API_BASE_URL);
  const response = await fetch(`${baseUrl}/api/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ region }),
  });

  if (!response.ok) {
    throw new Error(`Failed to refresh feed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get incidents for a specific region.
 * Calls GET /api/incidents on the backend.
 */
export async function getIncidents(
  region: string,
  limit: number = 100
): Promise<IncidentsResponse> {
  const params = new URLSearchParams({
    region,
    limit: limit.toString(),
  });

  const baseUrl = normalizeBaseUrl(API_BASE_URL);
  const response = await fetch(`${baseUrl}/api/incidents?${params}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get incidents: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get graph data for network visualization.
 * Calls GET /api/graph on the backend.
 */
export async function getGraph(region: string): Promise<GraphResponse> {
  const params = new URLSearchParams({ region });

  const baseUrl = normalizeBaseUrl(API_BASE_URL);
  const response = await fetch(`${baseUrl}/api/graph?${params}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get graph: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get map markers for geospatial visualization.
 * Calls GET /api/map on the backend.
 */
export async function getMap(region: string): Promise<MapResponse> {
  const params = new URLSearchParams({ region });

  const baseUrl = normalizeBaseUrl(API_BASE_URL);
  const response = await fetch(`${baseUrl}/api/map?${params}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get map: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Trigger asynchronous feed refresh for a specific region.
 * Returns immediately with a job ID for polling status.
 * Calls POST /api/refresh-async on the backend.
 */
export async function refreshFeedAsync(region: string): Promise<RefreshAsyncResponse> {
  const baseUrl = normalizeBaseUrl(API_BASE_URL);
  const response = await fetch(`${baseUrl}/api/refresh-async`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ region }),
  });

  if (!response.ok) {
    throw new Error(`Failed to start async refresh: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get status of an asynchronous refresh job.
 * Calls GET /api/refresh-status/{job_id} on the backend.
 */
export async function getRefreshStatus(jobId: string): Promise<RefreshStatusResponse> {
  const baseUrl = normalizeBaseUrl(API_BASE_URL);
  const response = await fetch(`${baseUrl}/api/refresh-status/${jobId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get refresh status: ${response.statusText}`);
  }

  return response.json();
}
