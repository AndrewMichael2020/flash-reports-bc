import os
import sys
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import SessionLocal
from app.models import Source
from app.main import get_parser  # uses same factory as app
# ...existing code...

def pprint_article(a, n=200):
    print("----")
    print("external_id:", getattr(a, "external_id", None))
    print("url:", getattr(a, "url", None))
    print("title_raw:", getattr(a, "title_raw", None))
    body = getattr(a, "body_raw", "")
    print("body length:", len(body))
    print("body (snippet):", (body or "")[:n].replace("\n", "\\n"))
    print("raw_html (snippet):", ((getattr(a, "raw_html", "") or "")[:n]).replace("\n","\\n"))
    print("published_at:", getattr(a, "published_at", None))
    print("----\n")

async def run_for_source(source_id=None, base_url=None):
    db = SessionLocal()
    try:
        if source_id:
            src = db.query(Source).filter(Source.id == int(source_id)).first()
        elif base_url:
            src = db.query(Source).filter(Source.base_url == base_url).first()
        else:
            print("Provide --source-id or --base-url")
            return
        if not src:
            print("Source not found")
            return
        print("Using source:", src.id, src.agency_name, src.base_url, "parser:", src.parser_id)
        parser = get_parser(src.parser_id)
        # call async fetch_new_articles(since=None)
        articles = await asyncio.wait_for(parser.fetch_new_articles(source_id=src.id, base_url=src.base_url, since=None), timeout=30)
        print(f"Parser returned {len(articles)} articles")
        for a in articles[:10]:
            pprint_article(a)
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--source-id", help="source id", type=int)
    p.add_argument("--base-url", help="base url")
    args = p.parse_args()
    asyncio.run(run_for_source(source_id=args.source_id, base_url=args.base_url))