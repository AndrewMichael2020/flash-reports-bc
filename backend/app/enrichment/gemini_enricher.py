"""
Gemini-based enrichment service for articles.
Extracts severity, summary, tags, entities, and location from raw articles.
"""
import os
import json
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

import yaml
from pathlib import Path
from app.logging_config import get_logger

logger = get_logger(__name__)


def _load_enrichment_config() -> dict:
    """
    Load enrichment configuration from backend/config/enrichment.yaml.
    Falls back to sane defaults if file missing or invalid.
    """
    # backend/app/enrichment/gemini_enricher.py -> backend/
    backend_dir = Path(__file__).resolve().parents[2]
    config_path = backend_dir / "config" / "enrichment.yaml"

    default = {
        "model_name": "gemini-1.5-flash",
        "prompt_version": "v1.0",
    }

    if not config_path.exists():
        return default

    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg = default.copy()
        cfg.update({k: v for k, v in data.items() if v is not None})
        return cfg
    except Exception:
        # On any parse error, just use defaults
        return default


class GeminiEnricher:
    """Enriches articles using Gemini Flash model."""
    
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY environment variable not set")
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        logger.info("GEMINI_API_KEY found, initializing Gemini client")
        cfg = _load_enrichment_config()
        
        try:
            self.client = genai.Client(api_key=api_key)
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
        
        self.model_name: str = cfg.get("model_name", "gemini-1.5-flash")
        self.prompt_version: str = cfg.get("prompt_version", "v1.0")
        logger.info(f"GeminiEnricher configured: model_name={self.model_name}, prompt_version={self.prompt_version}")
    
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
        - crime_category: str (default "Unknown")
        - temporal_context: str | None
        - weapon_involved: str | None
        - tactical_advice: str | None
        """
        
        prompt = f"""
You are a tactical analyst for police intelligence working with official police / RCMP news releases.
Your goal is to extract factual, citizen-focused metadata from incident reports.

Article Details:
- Agency: {agency}
- Region: {region}
- Published: {published_at or 'Unknown'}
- Title: {title}

Body (truncated to ~2000 chars):
{body[:2000]}

Tasks (STRICT):
1. Classify SEVERITY as exactly one of: LOW, MEDIUM, HIGH, CRITICAL.
   - CRITICAL: homicide, assassination, mass-casualty event, prison escape
   - HIGH: shootings, violent assaults, serious crashes with injuries
   - MEDIUM: robberies, break-ins, property crime with weapons
   - LOW: minor theft, mischief, non-injury incidents

2. Summary: A brief tactical summary (1-2 sentences) for law enforcement.

3. Tags: short category labels (e.g. ["Gang Activity","Trafficking","Shooting"]).

4. Entities: structured objects with type + name (e.g. gang, person, location).

5. Location: a human-readable label plus approximate latitude/longitude if inferable.

6. Graph cluster key: a short string used to group related incidents (e.g. "Surrey_dial_a_dope_war").

7. Crime Category: A citizen-friendly category (e.g. "Violent Crime", "Property Crime", "Traffic Incident", "Drug Offense", "Unknown"). Return "Unknown" if unsure.

8. Temporal Context: When the incident occurred in human terms (e.g. "Early morning hours", "During rush hour", "Late night"). Return null if not specified.

9. Weapon Involved: Type of weapon if mentioned (e.g. "Firearm", "Knife", "Vehicle as weapon", "None mentioned"). Return null if not mentioned or unclear.

10. Tactical Advice: Brief safety tip or context for citizens (e.g. "Avoid the area", "Increased patrols in effect", "No ongoing threat to public"). Return null if not applicable.

Return ONLY a single JSON object with this exact shape:
{{
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "summary_tactical": "string",
  "tags": ["string", ...],
  "entities": [
    {{"type": "Gang", "name": "UN Gang"}},
    {{"type": "Person", "name": "John Doe"}},
    {{"type": "Location", "name": "Whalley"}}
  ],
  "location_label": "string or null",
  "lat": 49.123 or null,
  "lng": -122.456 or null,
  "graph_cluster_key": "string or null",
  "crime_category": "string (default Unknown if unsure)",
  "temporal_context": "string or null",
  "weapon_involved": "string or null",
  "tactical_advice": "string or null"
}}
"""

        try:
            response = await self.client.models.generate_content_async(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            # Parse JSON response
            result = json.loads(response.text or "{}")

            # Validate required fields
            required_fields = ["severity", "summary_tactical", "tags", "entities"]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            return {
                "severity": result.get("severity", "MEDIUM"),
                "summary_tactical": result.get("summary_tactical", title[:150] if title else ""),
                "tags": result.get("tags") or [],
                "entities": result.get("entities") or [],
                "location_label": result.get("location_label"),
                "lat": result.get("lat"),
                "lng": result.get("lng"),
                "graph_cluster_key": result.get("graph_cluster_key"),
                # New citizen-facing fields with safe defaults
                "crime_category": result.get("crime_category") or "Unknown",
                "temporal_context": result.get("temporal_context"),
                "weapon_involved": result.get("weapon_involved"),
                "tactical_advice": result.get("tactical_advice"),
            }
            
        except Exception as e:
            logger.error(f"Enrichment failed for title='{title[:80]}...': {e}")
            # Return minimal valid enrichment
            return {
                "severity": "MEDIUM",
                "summary_tactical": title[:150] if title else "Article requires manual review",
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
