/**
 * Backend API client for Crimewatch Intel.
 * Provides functions to interact with the FastAPI backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface RefreshResponse {
  region: string;
  new_articles: number;
  total_incidents: number;
}

export interface IncidentsResponse {
  region: string;
  incidents: any[];
}

/**
 * Trigger feed refresh for a specific region.
 * Calls POST /api/refresh on the backend.
 */
export async function refreshFeed(region: string): Promise<RefreshResponse> {
  const response = await fetch(`${API_BASE_URL}/api/refresh`, {
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

  const response = await fetch(`${API_BASE_URL}/api/incidents?${params}`, {
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
