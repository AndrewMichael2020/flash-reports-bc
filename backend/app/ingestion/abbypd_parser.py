"""
Abbotsford Police Department (AbbyPD) parser.
Custom Playwright-backed parser for https://www.abbypd.ca/news-releases and article pages.
"""
import asyncio
import hashlib
import logging
from datetime import datetime
from typing import List, Optional, Dict
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.ingestion.parser_base import SourceParser, RawArticle
from app.ingestion.parser_utils import (
    retry_with_backoff,
    RetryConfig,
    parse_flexible_date,
    extract_main_content,
)

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except Exception as e:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright import failed in AbbyPDParser: %s", e)

ABBY_MAX_ARTICLES = 20


class AbbyPDParser(SourceParser):
    """Playwright-backed parser for Abbotsford Police Department (abbypd.ca)."""

    async def fetch_new_articles(
        self,
        source_id: int,
        base_url: str,
        since: Optional[datetime] = None,
    ) -> List[RawArticle]:
        if not PLAYWRIGHT_AVAILABLE:
            logger.error(
                "AbbyPDParser: Playwright not available. "
                "Install with: pip install playwright && playwright install chromium"
            )
            raise RuntimeError("Playwright not installed for AbbyPDParser")

        logger.info("AbbyPDParser.fetch_new_articles source_id=%s base_url=%s since=%s", source_id, base_url, since)

        articles: List[RawArticle] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                # Parse listing: /news-releases (AbbyPD uses month archive buttons)
                listing_items = await self._parse_listing(page, base_url)
                listing_items = listing_items[:ABBY_MAX_ARTICLES]

                for meta in listing_items:
                    if since and meta.get("published_at") and meta["published_at"] <= since:
                        continue

                    try:
                        async def fetch_detail():
                            return await self._parse_article(page, meta["url"])

                        config = RetryConfig(max_retries=2, initial_delay=1.0)
                        body_text, raw_html = await retry_with_backoff(fetch_detail, config)

                        if not body_text or len(body_text) < 50:
                            continue

                        key = (meta["url"] or "") + (meta["title"] or "")
                        external_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]

                        articles.append(
                            RawArticle(
                                external_id=external_id,
                                url=meta["url"],
                                title_raw=meta["title"],
                                published_at=meta.get("published_at"),
                                body_raw=body_text,
                                raw_html=raw_html[:10000] if raw_html else None,
                            )
                        )
                    except Exception as e:
                        logger.warning("AbbyPDParser: failed to fetch article %s: %s", meta.get("url"), e)
                        continue
            finally:
                await browser.close()

        return articles

    async def _parse_listing(self, page: Page, base_url: str) -> List[Dict]:
        """
        Fetch the /news-releases listing and extract article links + dates.

        AbbyPD structure:
        - /news-releases shows month buttons (JUNE 2025, JULY 2025, etc.).
        - Each month page lists individual releases under /blog/news_releases/<slug>.
        """
        await page.goto(base_url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1000)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        items: List[Dict] = []

        # Look for links into /blog/news_releases/ (actual news releases)
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            title = (a.get_text(strip=True) or "").strip()
            if not href or not title:
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            path = parsed.path.lower()

            # Only keep real news releases
            if "/blog/news_releases/" not in path:
                continue

            # Skip obvious nav/admin pages (covered by municipal static filters too)
            if len(title) < 10:
                continue

            # Try to infer date near the link (AbbyPD often shows date above title)
            published_at: Optional[datetime] = None
            parent = a.find_parent(["div", "li", "article"])
            if parent:
                # Look for date-like text (e.g. "December 5th, 2025")
                text = parent.get_text(" ", strip=True)
                published_at = parse_flexible_date(text)

            items.append(
                {
                    "url": full_url,
                    "title": title,
                    "published_at": published_at,
                }
            )

        # De-duplicate by URL
        seen = set()
        unique: List[Dict] = []
        for it in items:
            u = it["url"]
            if u in seen:
                continue
            seen.add(u)
            unique.append(it)

        return unique

    async def _parse_article(self, page: Page, url: str):
        """
        Fetch and extract the main body text from a single AbbyPD article page.
        """
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(500)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        selectors = [
            ".content",
            "#content",
            "article",
            "main",
            ".main-content",
        ]
        body_text = extract_main_content(soup, selectors)
        return body_text, html
