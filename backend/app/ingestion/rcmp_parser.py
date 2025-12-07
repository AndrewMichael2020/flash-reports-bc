"""
Playwright-backed RCMP parser for Crimewatch Intel backend.
Derived from tests/test_rcmp_news_parsing.py but returns RawArticle objects and is integrated
with the app ingestion workflow.

Behavior:
- If environment RCMP_TEST_JSON points to a path, use that file to return RawArticle entries (dev/test mode).
- Otherwise fetch listing and article pages via Playwright.
- Honors 'since' to filter out older articles.
"""
import os
import json
import re
import hashlib
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from app.ingestion.parser_base import SourceParser, RawArticle

# Optional Playwright import; we'll fail gracefully and raise helpful error if used without playwright installed
try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False

RCMP_MAX_ARTICLES = int(os.getenv("RCMP_MAX_ARTICLES", "20"))
RCMP_TEST_JSON = os.getenv("RCMP_TEST_JSON", "")  # If set, parse a JSON sample instead of network fetching


class RCMPParser(SourceParser):
    """
    RCMP parser implementing Playwright-based fetching of listing pages and article pages.
    Compatible with the project's SourceParser / RawArticle dataclass interfaces.
    """

    def __init__(self, use_playwright: Optional[bool] = True, allow_test_json: Optional[bool] = False):
        # allow_test_json: If True and RCMP_TEST_JSON env var is set, use local JSON for deterministic output.
        # Default is False so production/CLI flows use live Playwright scraping by default.
        self.use_playwright = bool(use_playwright)
        self.allow_test_json = bool(allow_test_json)
        # net base for rebuilding absolute URLs
        self.base_url = "https://rcmp.ca"

    async def fetch_new_articles(
        self,
        source_id: int,
        base_url: str,
        since: Optional[datetime] = None
    ) -> List[RawArticle]:
        """
        Fetch new articles for a source. Uses JSON sample file only if allow_test_json=True and RCMP_TEST_JSON set.
        """
        # If dev/test JSON loader explicitly allowed, prefer it because it's fast and deterministic for local testing
        if self.allow_test_json and RCMP_TEST_JSON:
            try:
                items = self._load_from_sample_json(RCMP_TEST_JSON, base_url)
                # Convert items to RawArticle and filter by 'since'
                return self._to_raw_article_list(items, since)
            except Exception as e:
                # Continue to playwright if sample file not parsable
                print(f"RCMPParser: failed loading sample JSON '{RCMP_TEST_JSON}': {e}")

        # If Playwright is not available, raise early to help debug misconfigured environments
        if self.use_playwright and not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed — please install with: pip install playwright && playwright install chromium")

        # Use Playwright to fetch listing & articles
        if self.use_playwright:
            return await self._fetch_via_playwright(base_url, since)
        else:
            # If playwright disabled, fallback to simple HTTP approach (best-effort)
            return await self._fetch_via_httpx(base_url, since)

    def _load_from_sample_json(self, json_path: str, listing_url: str) -> List[Dict[str, Any]]:
        """
        Read the sample JSON and return list of article dicts.
        Expects the same structure as tests/rcmp_news_output.json
        """
        path = json_path
        if not os.path.isabs(path):
            # Try relative to repo root (assumes running in workspace root)
            base = os.path.abspath(os.getcwd())
            path = os.path.join(base, path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Validate top-level match
        if not data or 'articles' not in data:
            raise ValueError("Invalid RCMP sample JSON format: missing 'articles'")
        items = []
        for a in data['articles']:
            items.append({
                'title': a.get('title'),
                'url': a.get('url'),
                'date_str': a.get('published_date'),
                'body': a.get('body', ""),
                'raw_html': None
            })
        return items

    def _to_raw_article_list(self, items: List[Dict[str, Any]], since: Optional[datetime]) -> List[RawArticle]:
        """
        Convert scraped item dictionaries into RawArticle dataclass list, applying 'since' filter.
        """
        raw_articles = []
        for item in items[:RCMP_MAX_ARTICLES]:
            published_at = None
            if item.get('date_str'):
                try:
                    published_at = date_parser.parse(item['date_str'])
                except Exception:
                    published_at = None
            # If we have since and the article is older or equal, skip it
            if since and published_at and published_at <= since:
                continue
            # compute external id
            key = (item['url'] or "") + (item.get('title') or "")
            external_id = hashlib.sha256(key.encode('utf-8')).hexdigest()[:32]
            raw_articles.append(RawArticle(
                external_id=external_id,
                url=item['url'],
                title_raw=item.get('title') or "",
                published_at=published_at,
                body_raw=(item.get('body') or ""),
                raw_html=item.get('raw_html')
            ))
        return raw_articles

    async def _fetch_via_playwright(self, listing_url: str, since: Optional[datetime]) -> List[RawArticle]:
        """
        Use Playwright to fetch the listing and then each article page.
        """
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
            page = await context.new_page()
            try:
                article_meta = await self._parse_listing_page(page, listing_url)
                article_meta = article_meta[:RCMP_MAX_ARTICLES]
                for meta in article_meta:
                    # parse the article page content
                    body, raw_html = await self._parse_article_page(page, meta['url'])
                    if not body or len(body) < 50:
                        continue
                    meta['body'] = body
                    meta['raw_html'] = raw_html[:10000] if raw_html else None
                    # apply 'since' filter
                    published_at = None
                    if meta.get('date_str'):
                        try:
                            published_at = date_parser.parse(meta['date_str'])
                        except Exception:
                            published_at = None
                    if since and published_at and published_at <= since:
                        continue
                    results.append(meta)
                    await asyncio.sleep(0.5)
            finally:
                await browser.close()

        return self._to_raw_article_list(results, since)

    async def _fetch_via_httpx(self, listing_url: str, since: Optional[datetime]) -> List[RawArticle]:
        """
        Fallback HTTP-based scraping using requests/bs4 if playwright is disabled/not available.
        This is best-effort and may not work for JS-heavy RCMP pages.
        """
        import httpx  # imported lazily
        items = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(listing_url, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = self._extract_articles_from_soup(soup, listing_url)
            results = []
            for meta in items[:RCMP_MAX_ARTICLES]:
                try:
                    r = await client.get(meta['url'], follow_redirects=True)
                    r.raise_for_status()
                    soup2 = BeautifulSoup(r.text, 'html.parser')
                    body = self._extract_article_content(soup2)
                    if not body or len(body) < 50:
                        continue
                    meta['body'] = body
                    meta['raw_html'] = r.text[:10000]
                    results.append(meta)
                except Exception:
                    continue
        return self._to_raw_article_list(results, since)

    async def _parse_listing_page(self, page: Page, listing_url: str) -> List[Dict[str, Any]]:
        """
        Use the Playwright page to fetch and parse article links from listing_url.
        """
        await page.goto(listing_url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1000)
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        return self._extract_articles_from_soup(soup, listing_url)

    async def _parse_article_page(self, page: Page, article_url: str):
        """
        Fetch and extract content from a single article page using Playwright.
        Returns (body_text, full_html)
        """
        await page.goto(article_url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(500)
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        return self._extract_article_content(soup), content

    def _extract_articles_from_soup(self, soup: BeautifulSoup, listing_url: str) -> List[Dict[str, Any]]:
        """
        Heuristics to extract article links / titles / dates from listing pages.

        This is intentionally aligned with tests/test_rcmp_news_parsing.py:
        - Prefer <article> / list/card structures.
        - Only keep links that look like real news items (contain /news/ and digits).
        - Filter out navigation/utility links like "Newsroom archive", "Social media", etc.
        """
        items: List[Dict[str, Any]] = []
        listing_url_norm = listing_url.rstrip("/")

        # Titles we never want (utility / nav links)
        BAD_TITLES = (
            "newsroom archive",
            "social media",
            "british columbia rcmp",
            "about this site",
        )

        def is_bad_title(title: str) -> bool:
            t = (title or "").strip().lower()
            if not t:
                return True
            if len(t) < 15:  # very short, almost always nav / non-article
                return True
            return any(bad in t for bad in BAD_TITLES)

        def is_article_href(href: str) -> bool:
            """
            Good RCMP articles typically are under /bc/<detachment>/news/ and contain some digits
            (year or id). Mirror the standalone test's /news/ + digits heuristic.
            """
            if not href:
                return False
            # full or relative path is fine; just check the path fragment
            path = href.split("://", 1)[-1]  # strip scheme if present
            # Must contain /news/ and at least one digit
            if "/news/" not in path:
                return False
            if not any(ch.isdigit() for ch in path):
                return False
            return True

        def to_full_url(href: str) -> Optional[str]:
            if not href:
                return None
            if href.startswith("http"):
                return href
            if href.startswith("/"):
                return urljoin(self.base_url, href)
            return None

        # Strategy 1: look for <article> and news card structures (as in the standalone script)
        for tag in soup.find_all(
            ["article", "li", "div"],
            class_=lambda x: x and ("news" in str(x).lower() or "article" in str(x).lower() or "item" in str(x).lower()),
        ):
            link = tag.find("a", href=True)
            if not link:
                continue
            href = link.get("href", "")
            title = link.get_text(strip=True)

            # Fallback to near heading if title is weak
            if not title or len(title) < 20:
                heading = tag.find(["h1", "h2", "h3", "h4"])
                if heading:
                    title = heading.get_text(strip=True)

            full_url = to_full_url(href)
            if not full_url:
                continue

            # Skip self-links to listing
            if full_url.rstrip("/") == listing_url_norm:
                continue

            # Heuristic filters
            if is_bad_title(title):
                continue
            if not is_article_href(full_url):
                continue

            # Extract date if present
            date_str = None
            time_elem = tag.find("time")
            if time_elem:
                date_str = time_elem.get("datetime") or time_elem.get_text(strip=True)
            else:
                text = tag.get_text()
                m = re.search(
                    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
                    text,
                )
                if m:
                    date_str = m.group(0)

            items.append({"title": title, "url": full_url, "date_str": date_str})

        # Strategy 2: if none, look for generic <a> with /news/ and digits (as in test_rcmp_news_parsing.py)
        if not items:
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if not is_article_href(href):
                    continue

                title = link.get_text(strip=True) or ""
                if len(title) < 20:
                    parent = link.find_parent(["article", "div", "li"])
                    if parent:
                        heading = parent.find(["h1", "h2", "h3", "h4"])
                        if heading:
                            title = heading.get_text(strip=True)

                if is_bad_title(title):
                    continue

                full_url = to_full_url(href)
                if not full_url:
                    continue
                if full_url.rstrip("/") == listing_url_norm:
                    continue

                items.append({"title": title, "url": full_url, "date_str": None})

        # Deduplicate by URL, preserving order
        unique: List[Dict[str, Any]] = []
        seen = set()
        for it in items:
            u = it["url"]
            if u in seen:
                continue
            seen.add(u)
            unique.append(it)

        return unique

    def _extract_article_content(self, soup: BeautifulSoup) -> str:
        """
        Extract main article text content from an article page soup.
        """
        for unwanted in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe', 'button']):
            unwanted.decompose()
        text = None
        article_elem = soup.find('article')
        if article_elem:
            text = article_elem.get_text(separator='\n', strip=True)
        if not text or len(text) < 200:
            main_elem = soup.find('main') or soup.find(id='main') or soup.find(class_=lambda x: x and 'main' in str(x).lower())
            if main_elem:
                text = main_elem.get_text(separator='\n', strip=True)
        if not text or len(text) < 200:
            content_elem = soup.find(class_=lambda x: x and ('content' in str(x).lower() or 'article' in str(x).lower()))
            if content_elem:
                text = content_elem.get_text(separator='\n', strip=True)
        if not text or len(text) < 200:
            body_elem = soup.find('body')
            if body_elem:
                text = body_elem.get_text(separator='\n', strip=True)
        if text:
            text = re.sub(r'\n\s*\n+', '\n\n', text)
            text = re.sub(r' +', ' ', text)
            return text.strip()
        return ""
