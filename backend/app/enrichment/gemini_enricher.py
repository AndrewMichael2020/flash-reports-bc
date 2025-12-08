"""
Gemini-based enrichment service for articles.
Extracts severity, summary, tags, entities, and location from raw articles.
"""
import os
import json
from typing import Optional, Dict, Any
from google import genai
from google.genai import types
import asyncio

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
        logger.info(
            "GeminiEnricher configured: model_name=%s, prompt_version=%s",
            self.model_name,
            self.prompt_version,
        )
    
    def _filter_entities(self, entities: Any) -> Any:
        """
        Remove obvious official names (ranks/titles) from entities, e.g.
        'Sergeant X', 'Constable Y', 'Inspector Z', etc.
        We keep organizations, locations, gangs, etc.
        """
        if not entities:
            return []

        filtered = []
        rank_keywords = [
            "sergeant",
            "sgt",
            "constable",
            "cst",
            "inspector",
            "insp",
            "corporal",
            "cpl",
            "chief",
            "deputy chief",
            "superintendent",
            "staff sergeant",
            "s/sgt",
            "officer",
        ]

        for ent in entities:
            # If model returned plain strings, keep them (we don't know what they are).
            if not isinstance(ent, dict):
                name = str(ent).strip().lower()
                if any(name.startswith(rk + " ") for rk in rank_keywords):
                    continue
                filtered.append(ent)
                continue

            etype = (ent.get("type") or "").lower()
            name = (ent.get("name") or "").strip()
            lname = name.lower()

            # If explicitly tagged as 'Person' and starts with a rank, drop it
            if etype in ("person", "officer"):
                if any(lname.startswith(rk + " ") for rk in rank_keywords):
                    continue

            filtered.append(ent)

        return filtered

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
        """
        
        prompt = f"""
You are a tactical analyst for police intelligence working with official police / RCMP news releases.
Your goal is to extract factual, citizen-focused metadata from incident reports.

STRICT ENTITY RULE:
- Extract ONLY non-person entities:
  - Criminal organizations / gangs / crews
  - Police agencies and units (e.g. "Langley RCMP", "Abbotsford Police Department")
  - Locations / neighbourhoods / landmarks
- DO NOT include named individuals or officials as entities:
  - Do NOT return police officers, mayors, spokespeople, witnesses, victims, or suspects by name
  - Example to EXCLUDE: "Sergeant Zynal Sharoom", "Constable Smith", "Mayor Doe"

Article Details:
- Agency: {agency}
- Region: {region}
- Published: {published_at or 'Unknown'}
- Title: {title}

Body (truncated to ~2000 chars):
{body[:2000]}

Tasks (STRICT):
1. Classify SEVERITY as exactly one of: LOW, MEDIUM, HIGH, CRITICAL.
   - CRITICAL: homicide, assassination, mass-casualty event, prison escape, active shooter
   - HIGH: shootings, stabbings, violent assaults, serious crashes with injuries, armed robbery, domestic violence with weapons
   - MEDIUM: robberies, break-ins, property crime with weapons, drug trafficking, assault without weapons, DUI with injury
   - LOW: minor theft, mischief, fraud, drug possession, traffic violations, non-injury incidents

2. Summary: A brief tactical summary (1-2 sentences) for law enforcement.

3. Tags: short category labels (e.g. ["Traffic", "Collision", "Drug Trafficking"]).

4. Entities: structured objects with type + name.
   - Use types like: "Gang", "Organization", "Agency", "Location"
   - DO NOT include any "Person" entities or named officials.

5. Location: a human-readable label plus approximate latitude/longitude if inferable.

6. Graph cluster key: a short string used to group related incidents (e.g. "Surrey_dial_a_dope_war").

7. Crime Category: A citizen-friendly category. Choose from:
   - "Violent Crime"
   - "Property Crime"
   - "Traffic Incident"
   - "Drug Offense"
   - "Sexual Offense"
   - "Cybercrime"
   - "Public Safety"
   - "Other"
   - "Unknown"

8. Temporal Context: When the incident occurred in human terms (e.g. "Early morning hours", "During rush hour", "Late night"). Return null if not specified.

9. Weapon Involved: Type of weapon if mentioned (e.g. "Firearm", "Knife", "Vehicle as weapon", "Blunt object", "None mentioned"). Return null if not mentioned or unclear.

10. Tactical Advice: Brief safety tip or context for citizens (e.g. "Avoid the area", "Increased patrols in effect", "No ongoing threat to public", "Suspect in custody"). Return null if not applicable.

Return ONLY a single JSON object with this exact shape:
{{
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "summary_tactical": "string",
  "tags": ["string", ...],
  "entities": [
    {{"type": "Organization", "name": "Langley RCMP"}},
    {{"type": "Agency", "name": "Abbotsford Police Department"}},
    {{"type": "Location", "name": "264 Street and 0 Avenue, Langley"}}
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
            logger.debug(
                "Calling Gemini model=%s prompt_version=%s for title='%s...'",
                self.model_name,
                self.prompt_version,
                (title or "")[:40],
            )

            # Run the blocking SDK call in a worker thread (no generate_content_async in this SDK)
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            # Prefer response.text, but fall back to candidate text if needed
            raw_text = getattr(response, "text", None)
            if not raw_text and getattr(response, "candidates", None):
                try:
                    first = response.candidates[0]
                    parts = getattr(first, "content", getattr(first, "parts", None))
                    if hasattr(parts, "parts"):
                        parts = parts.parts
                    if parts:
                        raw_text = getattr(parts[0], "text", None)
                except Exception as parse_fallback_err:
                    logger.warning("Failed to extract text from candidates: %s", parse_fallback_err)

            if not raw_text:
                raise ValueError("Gemini response did not contain text to parse as JSON")

            try:
                result = json.loads(raw_text)
            except json.JSONDecodeError as je:
                logger.error(
                    "Failed to parse Gemini JSON for title='%s...': %s | raw: %s",
                    (title or "")[:40],
                    je,
                    raw_text[:500],
                )
                raise

            # Validate required fields
            required_fields = ["severity", "summary_tactical", "tags", "entities"]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field in Gemini result: {field}")

            # Apply entity filtering
            raw_entities = result.get("entities") or []
            filtered_entities = self._filter_entities(raw_entities)

            return {
                "severity": result.get("severity", "MEDIUM"),
                "summary_tactical": result.get("summary_tactical", title[:150] if title else ""),
                "tags": result.get("tags") or [],
                "entities": filtered_entities,
                "location_label": result.get("location_label"),
                "lat": result.get("lat"),
                "lng": result.get("lng"),
                "graph_cluster_key": result.get("graph_cluster_key"),
                "crime_category": result.get("crime_category") or "Unknown",
                "temporal_context": result.get("temporal_context"),
                "weapon_involved": result.get("weapon_involved"),
                "tactical_advice": result.get("tactical_advice"),
            }

        except Exception as e:
            logger.error(
                "Enrichment failed for title='%s...': %s",
                (title or "")[:80],
                e,
            )
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
