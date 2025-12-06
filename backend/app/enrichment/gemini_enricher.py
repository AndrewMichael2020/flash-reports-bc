"""
Gemini-based enrichment service for articles.
Extracts severity, summary, tags, entities, and location from raw articles.
"""
import os
import json
from typing import Optional, Dict, Any
from google import genai
from google.genai import types


class GeminiEnricher:
    """Enriches articles using Gemini Flash model."""
    
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-1.5-flash"
        self.prompt_version = "v1.0"
    
    async def enrich_article(
        self,
        title: str,
        body: str,
        agency: str,
        region: str,
        published_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich a single article with structured intelligence.
        
        Returns dict with keys:
        - severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
        - summary_tactical: str
        - tags: list[str]
        - entities: list[dict]
        - location_label: str | None
        - lat: float | None
        - lng: float | None
        - graph_cluster_key: str | None
        """
        
        prompt = f"""You are a tactical analyst for police intelligence. Analyze this police news release and extract structured intelligence.

**Article Details:**
Agency: {agency}
Region: {region}
Published: {published_at or 'Unknown'}
Title: {title}

**Body:**
{body[:2000]}

**Tasks:**
1. **Severity Classification** (choose ONE):
   - CRITICAL: Homicide, assassination, mass casualty, prison escape, cop killer, active shooter
   - HIGH: Gang shooting, armed robbery, kidnapping, carjacking ring, missing person (suspicious), major drug bust
   - MEDIUM: Drug bust, industrial theft, weapon seizure, organized theft ring
   - LOW: Non-violent property crime, minor incidents

2. **Tactical Summary**: One-sentence summary suitable for intelligence briefing (max 150 chars)

3. **Tags**: Select 2-4 tags from: [Homicide, Gang Activity, Trafficking, Escape, Armed Assault, Carjacking, Missing Person, Theft Ring, Drug Bust, Weapons Seizure, Organized Crime]

4. **Entities**: Extract specific entities (gang names, key individuals, specific locations/landmarks). Format as list of objects with "type" (Person, Group, Location) and "name".

5. **Location**: Extract the most specific location mentioned. Estimate latitude/longitude coordinates for the location within {region}.

6. **Graph Cluster**: Suggest a cluster/theme key if this relates to a larger pattern (e.g., "Fraser Valley Gang War", "Highway 1 Trafficking Ring", or null if standalone).

**Output Format (JSON only, no markdown):**
{{
  "severity": "HIGH",
  "summary_tactical": "Armed robbery at commercial premises, suspects fled",
  "tags": ["Armed Assault", "Organized Crime"],
  "entities": [
    {{"type": "Location", "name": "Industrial Ave, Langley"}},
    {{"type": "Group", "name": "Suspect gang affiliation"}}
  ],
  "location_label": "Langley, BC - Industrial Ave",
  "lat": 49.1042,
  "lng": -122.6604,
  "graph_cluster_key": "Fraser Valley Property Crime"
}}
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            
            # Parse JSON response
            result = json.loads(response.text)
            
            # Validate required fields
            required_fields = ["severity", "summary_tactical", "tags", "entities"]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            return result
            
        except Exception as e:
            print(f"Enrichment failed: {e}")
            # Return minimal valid enrichment
            return {
                "severity": "MEDIUM",
                "summary_tactical": title[:150] if title else "Article requires manual review",
                "tags": [],
                "entities": [],
                "location_label": None,
                "lat": None,
                "lng": None,
                "graph_cluster_key": None
            }
