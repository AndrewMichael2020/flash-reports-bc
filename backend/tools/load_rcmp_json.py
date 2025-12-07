#!/usr/bin/env python3
"""
Run RCMP parser (Playwright) for a configured source and insert new articles into DB.
Defaults to live parsing. Use --json-file to explicitly load a JSON sample.
"""
import os
import sys
import argparse
import json
import hashlib
import asyncio
from datetime import datetime
from typing import Optional, List
from dateutil import parser as date_parser

# Ensure backend dir is on sys.path so imports like `from app.db import ...` work
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.db import SessionLocal
from app.models import Source, ArticleRaw, IncidentEnriched
from sqlalchemy.orm import load_only
from sqlalchemy import inspect
from app.ingestion.rcmp_parser import RCMPParser
from app.ingestion.parser_base import RawArticle
from sqlalchemy.exc import IntegrityError

ENV = os.getenv("ENV", "dev").lower()

def compute_external_id(url: str, title: str) -> str:
    key = (url or "") + (title or "")
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]

def get_simple_source_by_id(session, source_id: int) -> Optional[Source]:
    # Load minimal fields only to avoid selecting optional columns that might not exist
    return session.query(Source).options(
        load_only(Source.id, Source.agency_name, Source.base_url, Source.parser_id, Source.active, Source.region_label)
    ).filter(Source.id == source_id).first()

def ensure_source(session, base_url: str, create_source: bool) -> Source:
    # Schema aware lookup and optional create
    inspector = inspect(session.bind)
    col_names = {c['name'] for c in inspector.get_columns('sources')}

    src = session.query(Source).options(
        load_only(
            Source.id, Source.agency_name, Source.jurisdiction, Source.region_label,
            Source.source_type, Source.base_url, Source.parser_id, Source.active
        )
    ).filter(Source.base_url == base_url).first()

    if src:
        return src

    if not create_source:
        raise ValueError("Source not found and --create-source not set")

    # Create minimal source
    agency_name = "RCMP (unknown)"
    try:
        parts = base_url.split('/')
        agency_name = parts[-2].replace('-', ' ').title() + " RCMP"
    except Exception:
        pass

    new_source_kwargs = dict(
        agency_name=agency_name,
        jurisdiction="BC",
        region_label="Unknown",
        source_type="RCMP_NEWSROOM",
        base_url=base_url,
        parser_id="rcmp",
        active=True,
    )

    # IMPORTANT: do NOT set use_playwright here at all; it may not exist in SQLite schema.
    # Only include columns that actually exist in the DB schema
    filtered_kwargs = {k: v for k, v in new_source_kwargs.items() if k in col_names}

    # Use Core insert to avoid ORM auto-including unmapped columns
    insert_stmt = Source.__table__.insert().values(**filtered_kwargs)
    session.execute(insert_stmt)
    session.commit()

    # Fetch the ORM object for further operations
    src = session.query(Source).filter(Source.base_url == base_url).first()
    return src

def insert_article_and_enrichment(session, src_id: int, article: RawArticle) -> bool:
    existing = session.query(ArticleRaw).filter(
        ArticleRaw.source_id == src_id,
        ArticleRaw.external_id == article.external_id
    ).first()
    if existing:
        return False

    ar = ArticleRaw(
        source_id=src_id,
        external_id=article.external_id,
        url=article.url,
        title_raw=article.title_raw,
        published_at=article.published_at,
        body_raw=article.body_raw,
        raw_html=article.raw_html
    )
    session.add(ar)
    session.flush()

    summary_tactical = (article.body_raw[:200] if article.body_raw else article.title_raw[:200])
    enriched = IncidentEnriched(
        id=ar.id,
        severity="MEDIUM",
        summary_tactical=summary_tactical,
        tags=[],
        entities=[],
        location_label=None,
        lat=None,
        lng=None,
        graph_cluster_key=None,
        llm_model="none",
        prompt_version="dummy_v1"
    )
    session.add(enriched)

    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False

def parse_json_file(file_path: str) -> List[RawArticle]:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    articles = []
    for a in data.get('articles', []):
        published_at = None
        if a.get('published_date'):
            try:
                published_at = date_parser.parse(a.get('published_date'))
            except Exception:
                published_at = None
        ext_id = compute_external_id(a.get('url', ''), a.get('title', ''))
        articles.append(RawArticle(
            external_id=ext_id,
            url=a.get('url'),
            title_raw=a.get('title', '') or "",
            published_at=published_at,
            body_raw=a.get('body', '') or "",
            raw_html=a.get('raw_html')
        ))
    return articles

def run_parser_live(session, src: Source, since: Optional[datetime]) -> (int, int):
    # Use RCMPParser live (no loading of test JSON)
    parser = RCMPParser(use_playwright=True, allow_test_json=False)
    try:
        fetched: List[RawArticle] = asyncio.run(parser.fetch_new_articles(source_id=src.id, base_url=src.base_url, since=since))
    except Exception as e:
        raise RuntimeError(f"RCMP parser failed: {e}")

    inserted = 0
    skipped = 0
    for article in fetched:
        if insert_article_and_enrichment(session, src.id, article):
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped

def run_json_insert(session, src_id: int, file_path: str) -> (int, int):
    articles = parse_json_file(file_path)
    inserted = 0
    skipped = 0
    for article in articles:
        if insert_article_and_enrichment(session, src_id, article):
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped

def main():
    parser = argparse.ArgumentParser(description="Run RCMP parser and insert results into DB (defaults to live parser).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source-id", type=int, help="Existing source ID (use this to select a configured source)")
    group.add_argument("--base-url", type=str, help="Base URL of source (e.g., https://rcmp.ca/en/bc/langley/news)")
    parser.add_argument("--json-file", type=str, default=None, help="Optional JSON sample file to insert instead of live parsing")
    parser.add_argument("--create-source", action="store_true", help="Create a new Source if base-url not found")
    parser.add_argument("--confirm", action="store_true", help="Confirm (required if ENV != dev)")
    args = parser.parse_args()

    if ENV != "dev" and not args.confirm:
        print(f"ENV != 'dev' ({ENV}) - must pass --confirm to run")
        sys.exit(1)

    session = SessionLocal()
    try:
        if args.source_id:
            src = get_simple_source_by_id(session, args.source_id)
            if not src:
                print(f"Source id={args.source_id} not found")
                sys.exit(2)
        else:
            src = ensure_source(session, args.base_url, create_source=args.create_source)

        latest_article = session.query(ArticleRaw).filter(ArticleRaw.source_id == src.id).order_by(ArticleRaw.published_at.desc()).first()
        since = latest_article.published_at if latest_article else None

        if args.json_file:
            inserted, skipped = run_json_insert(session, src.id, args.json_file)
        else:
            inserted, skipped = run_parser_live(session, src, since=since)

        print(f"Done. Inserted: {inserted}, Skipped (duplicates): {skipped}")
    finally:
        session.close()

if __name__ == "__main__":
    main()