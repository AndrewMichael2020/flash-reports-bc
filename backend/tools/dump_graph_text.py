#!/usr/bin/env python3
"""
Dump a text view of the incident "mind map" for a region.

Example:
  cd backend
  source venv/bin/activate
  python tools/dump_graph_text.py --region "Fraser Valley, BC"
"""
import os
import sys
import argparse

# Ensure backend package path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db import SessionLocal
from app.models import Source, ArticleRaw, IncidentEnriched


def dump_region(region: str) -> None:
    session = SessionLocal()
    try:
        rows = (
            session.query(ArticleRaw, IncidentEnriched, Source)
            .join(IncidentEnriched, ArticleRaw.id == IncidentEnriched.id)
            .join(Source, ArticleRaw.source_id == Source.id)
            .filter(Source.region_label == region)
            .order_by(ArticleRaw.id.asc())
            .all()
        )

        if not rows:
            print(f"No incidents found for region: {region}")
            return

        print(f"=== Mind-map text view for region: {region} ===\n")

        for article, enriched, source in rows:
            print(f"[{article.id}] {source.agency_name} — {article.title_raw}")
            if article.published_at:
                print(f"  reported: {article.published_at.isoformat()}")
            if enriched.incident_occurred_at:
                print(f"  event:    {enriched.incident_occurred_at.isoformat()}")

            # Location node
            if enriched.location_label:
                print(f"  location: {enriched.location_label}")

            # Entity nodes
            if enriched.entities:
                print("  entities:")
                for ent in enriched.entities:
                    if isinstance(ent, dict):
                        et = ent.get("type", "?")
                        nm = ent.get("name", "?")
                        print(f"    - {et}: {nm}")
                    else:
                        print(f"    - {ent}")
            else:
                print("  entities: (none)")

            print()
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Dump text view of incident mind map for a region.")
    parser.add_argument("--region", required=True, help="Region label, e.g. 'Fraser Valley, BC'")
    args = parser.parse_args()
    dump_region(args.region)


if __name__ == "__main__":
    main()
