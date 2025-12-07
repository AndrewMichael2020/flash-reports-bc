#!/usr/bin/env python3
"""
CLI tool to query the backend DB and display full article text for a given region.
Useful to test whether the fetched content is the actual article vs. site "About"/"Contact" pages.
"""

import os
import sys
import textwrap
import argparse
from typing import Optional
from sqlalchemy import or_

# Ensure the backend project root (parent of this tools/ directory) is on sys.path so "app" package is importable.
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import DB session provider and models from the backend
try:
    from app.db import get_db
    from app.models import ArticleRaw, Source, IncidentEnriched
except Exception as e:
    # Helpful guidance if the environment/path not set up
    print("[cli_show_articles] Failed to import app package (are you running from the backend directory?).")
    print(f"[cli_show_articles] Current working dir: {os.getcwd()}")
    print(f"[cli_show_articles] Tried to add project_root to sys.path: {project_root}")
    raise


# Default newsroom filter:
# Paste a single newsroom base URL or agency name directly here for quick testing.
# Example values:
# DEFAULT_NEWSROOM_URL = "https://www.examplepolice.ca/newsroom"
# DEFAULT_NEWSROOM_URL = "City of Example Police Department"
DEFAULT_NEWSROOM_URL = "https://rcmp.ca/en/bc/langley/news"  
# <-- Paste your newsroom URL/agency name here


def looks_like_full_article(text: Optional[str]) -> bool:
    """
    Heuristic to decide whether text looks like a full article.
    Returns True if likely full article; False if likely a short site page (About/Contact/etc).
    """
    if not text:
        return False
    t = text.strip()
    if len(t) < 200:
        return False  # too short to be a full article
    lower = t.lower()
    # early negative indicators commonly found in site pages
    negative_phrases = [
        "about", "contact", "cookie", "privacy", "terms", "mission", "our mission",
        "subscribe", "follow us", "join us", "who we are", "our story"
    ]
    # If the beginning starts with one of these or they appear in first ~200 chars,
    # it's likely a site page rather than a news article.
    preview = lower[:300]
    for p in negative_phrases:
        if preview.startswith(p) or p in preview:
            return False
    # Require at least a few sentences
    sentence_count = t.count('.') + t.count('!') + t.count('?')
    if sentence_count < 3 and t.count('\n') < 3:
        return False
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="CLI: show full article text from DB for a region.")
    parser.add_argument("--region", "-r", required=True, help="Region label (e.g., 'Fraser Valley, BC')")
    parser.add_argument("--limit", "-n", type=int, default=50, help="Max number of articles to fetch")
    parser.add_argument("--truncate", "-t", type=int, default=2000, help="Max chars of full text to display (0 = no truncation)")
    parser.add_argument("--suspicious-only", "-s", action="store_true", help="Show only articles that appear suspicious (likely not full articles)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--newsroom-url", "-u", default=None, help="Filter to a single newsroom base URL or agency name (overrides DEFAULT_NEWSROOM_URL in this file)")
    return parser.parse_args()


def main():
    args = parse_args()
    region = args.region
    limit = args.limit
    truncate = args.truncate
    suspicious_only = args.suspicious_only
    verbose = args.verbose
    # Command-line argument overrides the pasted DEFAULT_NEWSROOM_URL constant.
    newsroom_filter = args.newsroom_url or DEFAULT_NEWSROOM_URL

    # Inform the user which newsroom filter will be used for this run.
    if newsroom_filter:
        print(f"[cli_show_articles] Using newsroom filter: {newsroom_filter}")
    else:
        print("[cli_show_articles] No newsroom filter applied; searching all newsrooms for the provided region.")

    db = next(get_db())
    try:
        # Query articles for the region (join enriched and source to get context)
        q = db.query(
            ArticleRaw, IncidentEnriched, Source
        ).join(
            IncidentEnriched, ArticleRaw.id == IncidentEnriched.id
        ).join(
            Source, ArticleRaw.source_id == Source.id
        ).filter(
            Source.region_label == region
        )

        # If a newsroom filter is supplied, narrow results to that newsroom by base_url or agency name.
        if newsroom_filter:
            q = q.filter(
                or_(
                    Source.base_url.ilike(f"%{newsroom_filter}%"),
                    Source.agency_name.ilike(f"%{newsroom_filter}%")
                )
            )

        # Apply ordering and limit last
        q = q.order_by(ArticleRaw.published_at.desc()).limit(limit)

        rows = q.all()
        if not rows:
            print(f"No incidents found for region: {region}")
            return

        for article, enriched, source in rows:
            full_text = article.body_raw or enriched.summary_tactical or ""
            is_full = looks_like_full_article(full_text)
            if suspicious_only and is_full:
                continue

            # Short metadata header
            print("=" * 120)
            print(f"ID   : {article.id}")
            print(f"Source: {source.agency_name} ({source.source_type})")
            print(f"Region: {source.region_label}")
            if article.published_at:
                print(f"Published: {article.published_at.isoformat()}")
            print(f"URL  : {article.url}")
            if article.title_raw:
                print(f"Title: {article.title_raw}")
            print(f"Likely Full Article: {is_full}")
            if verbose:
                print(f"Severity: {enriched.severity}, Tags: {enriched.tags}, Entities: {enriched.entities}")
            print("-" * 120)

            display_text = full_text
            if truncate and truncate > 0:
                display_text = full_text[:truncate]
            if not display_text:
                print("[No full text available]")
            else:
                print(textwrap.fill(display_text, width=100))
            print("\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()