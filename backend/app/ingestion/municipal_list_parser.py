"""
Municipal List Parser.
Handles municipal police newsroom sites with list-style layouts (e.g., Surrey PD, Abbotsford PD).
"""
import httpx
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List
import hashlib
import re
from urllib.parse import urljoin, urlparse

from app.ingestion.parser_base import SourceParser, RawArticle
from app.ingestion.parser_utils import (
    retry_with_backoff, RetryConfig,
    parse_flexible_date, extract_main_content, clean_html_text
)

# Set up logger
logger = logging.getLogger(__name__)


class MunicipalListParser(SourceParser):
    """Parser for municipal police newsrooms with list/card layouts."""
    
    async def fetch_new_articles(
        self,
        source_id: int,
        base_url: str,
        since: Optional[datetime] = None
    ) -> List[RawArticle]:
        """
        Fetch new articles from a municipal newsroom with list layout.
        
        These sites typically have cards or list items with news releases.
        """
        articles = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fetch the newsroom listing page with retry
                async def fetch_listing():
                    response = await client.get(base_url, follow_redirects=True)
                    response.raise_for_status()
                    return response
                
                config = RetryConfig(max_retries=2, initial_delay=1.0)
                response = await retry_with_backoff(fetch_listing, config)
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find news items
                news_items = self._extract_news_items(soup, base_url)
                
                for item in news_items:
                    # Check if we should stop based on date
                    if since and item['published_at'] and item['published_at'] <= since:
                        break
                    
                    # Fetch the full article with retry
                    article = await self._fetch_article_detail(client, item)
                    if article:
                        articles.append(article)
                 
        except Exception as e:
            logger.error(f"Error fetching municipal articles: {e}")
            
        return articles
    
    def _extract_news_items(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        """
        Extract news items from municipal list/card layout.
        Returns list of dicts with url, title, published_at.
        """
        items = []

        parsed_base = urlparse(base_url)
        host = (parsed_base.netloc or "").lower()

        # Helper: Surrey-specific static-page filter
        def is_surrey_static(title: str, href: str) -> bool:
            """
            Filter out known Surrey Police Service non-incident pages:
            Make a Report, When To Call Police, Community Programs, etc.
            """
            if "surreypolice.ca" not in host:
                return False

            t = (title or "").strip().lower()
            h = (href or "").strip().lower()

            # Title-based heuristics (from your feed)
            static_title_keywords = [
                "make a report",
                "when to call police",
                "community programs",
                "block watch",
                "community input",
                "community 1st",
                "community 1st.",  # in case of punctuation
                "community first",
                "youth services",
                "civilian oversight",
                "filing a complaint",
                "body-worn cameras",
                "body worn cameras",
                "procurement and bids",
                "information and privacy",
                "remotely piloted aircraft",
            ]
            if any(kw in t for kw in static_title_keywords):
                return True

            # URL slug-based heuristics
            static_slug_keywords = [
                "make-a-report",
                "when-to-call-police",
                "community-programs",
                "block-watch",
                "community-input",
                "community-1st",
                "community-first",
                "youth-services",
                "civilian-oversight",
                "filing-a-complaint",
                "body-worn-cameras",
                "procurement-and-bids",
                "information-and-privacy",
                "remotely-piloted-aircraft",
            ]
            return any(kw in h for kw in static_slug_keywords)

        # NEW: Abbotsford PD static-page filter
        def is_abbypd_static(title: str, href: str) -> bool:
            """
            Filter out known Abbotsford PD non-incident / admin pages:
            board members, meeting schedule, history, foundation, etc.
            """
            if "abbypd.ca" not in host:
                return False

            t = (title or "").strip().lower()
            h = (href or "").strip().lower()

            title_keywords = [
                "police board members",
                "police board",
                "meeting schedule",
                "minutes",
                "previous years",
                "our history",
                "progress gallery",
                "message from the chief",
                "abbotsford police foundation",
                "foundation",
                "about us",
                "organization structure",
                "governance",
            ]
            if any(kw in t for kw in title_keywords):
                return True

            slug_keywords = [
                "police-board",
                "board-members",
                "meeting-schedule",
                "minutes",
                "our-history",
                "progress-gallery",
                "message-from-the-chief",
                "abbotsford-police-foundation",
                "foundation",
            ]
            return any(kw in h for kw in slug_keywords)

        # Look for common patterns in municipal sites
        # Try card-style layouts first
        cards = soup.find_all(['div', 'article', 'li'], class_=lambda c: c and (
            'card' in c.lower() or 
            'news' in c.lower() or 
            'release' in c.lower() or
            'item' in c.lower()
        ) if c else False)
        
        # If no cards, look for table rows or list items
        if not cards:
            cards = soup.find_all(['tr', 'li', 'div'], class_=lambda c: True)
        
        for card in cards[:20]:  # Limit to 20 most recent
            # Find the title link
            title_link = card.find('a', href=True)
            
            # Try finding in headings
            if not title_link:
                for heading in card.find_all(['h2', 'h3', 'h4', 'h5']):
                    title_link = heading.find('a', href=True)
                    if title_link:
                        break
            
            if not title_link:
                continue
            
            title = title_link.get_text(strip=True)
            href = title_link.get('href', '')
            
            # Filter out navigation links and non-news content
            if not title or not href or len(title) < 10:
                continue
            
            # Skip non-HTTP(S) links (tel:, mailto:, javascript:, etc.)
            if href.startswith(('tel:', 'mailto:', 'javascript:', '#')):
                continue
            
            # Skip if it looks like a navigation link
            if any(word in title.lower() for word in ['home', 'about', 'contact', 'menu', 'search']):
                continue

            # Surrey-specific: drop known static / program pages
            if is_surrey_static(title, href):
                logger.debug("MunicipalListParser: dropping Surrey static page title=%r href=%r", title, href)
                continue

            # Abbotsford-specific: drop known static / admin pages
            if is_abbypd_static(title, href):
                logger.debug("MunicipalListParser: dropping Abbotsford static page title=%r href=%r", title, href)
                continue
            
            # Build full URL
            if not href.startswith('http'):
                href = urljoin(base_url, href)
            
            # Final validation - ensure it's a valid HTTP(S) URL
            if not href.startswith(('http://', 'https://')):
                continue
            
            # Try to extract date
            published_at = None
            
            # Look for date in various places
            date_elem = card.find(class_=lambda c: c and 'date' in c.lower() if c else False)
            if date_elem:
                published_at = self._parse_date(date_elem.get_text())
            
            # Try time element
            if not published_at:
                time_elem = card.find('time')
                if time_elem:
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        published_at = self._parse_date(datetime_attr)
                    else:
                        published_at = self._parse_date(time_elem.get_text())
            
            # Try finding date in card text
            if not published_at:
                card_text = card.get_text()
                published_at = self._parse_date(card_text)
            
            items.append({
                'url': href,
                'title': title,
                'published_at': published_at
            })
        
        # Surrey-specific fallback: if nothing found yet, try a looser pattern
        if not items and "surreypolice.ca" in host:
            logger.debug("MunicipalListParser: Surrey fallback selector engaged for %s", base_url)
            # Look for anchors under /news-releases/ in main content
            main = soup.find('main') or soup.find('div', id='main-content') or soup
            for a in main.find_all('a', href=True):
                href = a.get('href', '')
                title = a.get_text(strip=True)
                if not title or len(title) < 10:
                    continue
                if 'news-releases' not in href:
                    continue
                if is_surrey_static(title, href):
                    continue
                if not href.startswith('http'):
                    href_full = urljoin(base_url, href)
                else:
                    href_full = href
                if not href_full.startswith(('http://', 'https://')):
                    continue
                # Do NOT attempt to parse date here; let published_at be None
                items.append({
                    'url': href_full,
                    'title': title,
                    'published_at': None,
                })

        return items
    
    def _parse_date(self, text: str) -> Optional[datetime]:
        """
        Attempt to parse a date from text.
        Uses shared date parsing utility for consistency.
        """
        return parse_flexible_date(text)
    
    async def _fetch_article_detail(
        self,
        client: httpx.AsyncClient,
        item: dict
    ) -> Optional[RawArticle]:
        """
        Fetch the full content of an article from its detail page.
        Uses retry logic for robustness.
        """
        try:
            async def fetch_detail():
                response = await client.get(item['url'], follow_redirects=True)
                response.raise_for_status()
                return response
            
            config = RetryConfig(max_retries=2, initial_delay=1.0)
            response = await retry_with_backoff(fetch_detail, config)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract main content using shared utility
            body_raw = self._extract_body(soup)
            
            if not body_raw or len(body_raw) < 50:
                return None
            
            # Generate external_id as hash of URL + title
            external_id = hashlib.sha256(
                (item['url'] + item['title']).encode('utf-8')
            ).hexdigest()[:32]
            
            return RawArticle(
                external_id=external_id,
                url=item['url'],
                title_raw=item['title'],
                published_at=item.get('published_at'),
                body_raw=body_raw,
                raw_html=response.text[:10000]
            )
            
        except Exception as e:
            logger.warning(f"Error fetching article detail from {item['url']}: {e}")
            return None
    
    def _extract_body(self, soup: BeautifulSoup) -> str:
        """
        Extract the main text content from an article page.
        Uses shared content extraction utility for consistency.
        """
        # Use shared utility with municipal-specific selectors
        selectors = [
            '.content',
            '#content',
            'article',
            'main',
            '.main-content',
            '.news-content',
            '.release-content',
            '.post-content'
        ]
        
        return extract_main_content(soup, selectors)
