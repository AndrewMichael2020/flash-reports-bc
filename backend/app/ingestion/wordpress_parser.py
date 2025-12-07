"""
WordPress Parser.
Handles WordPress-based police newsroom sites (e.g., VPD).
"""
import httpx
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List
import hashlib
import re
from urllib.parse import urljoin

from app.ingestion.parser_base import SourceParser, RawArticle
from app.ingestion.parser_utils import (
    retry_with_backoff, RetryConfig,
    parse_flexible_date, extract_main_content, clean_html_text
)

# Set up logger
logger = logging.getLogger(__name__)


class WordPressParser(SourceParser):
    """Parser for WordPress-based newsrooms."""
    
    async def fetch_new_articles(
        self,
        source_id: int,
        base_url: str,
        since: Optional[datetime] = None
    ) -> List[RawArticle]:
        """
        Fetch new articles from a WordPress newsroom.
        
        WordPress sites typically have consistent HTML structure with
        article listings and links to detail pages.
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
                
                # Find news items (WordPress typically uses article tags or post classes)
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
            logger.error(f"Error fetching WordPress articles: {e}")
            
        return articles
    
    def _extract_news_items(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        """
        Extract news items from WordPress listing page.
        Returns list of dicts with url, title, published_at.
        """
        items = []
        
        # Common WordPress selectors
        # Try article tags first (most common in modern WP themes)
        articles = soup.find_all('article')
        
        if not articles:
            # Fallback to common post classes
            articles = soup.find_all(['div', 'li'], class_=lambda c: c and ('post' in c or 'article' in c or 'news' in c))
        
        for article_elem in articles[:20]:  # Limit to 20 most recent
            # Find the title link
            title_link = article_elem.find('a', href=True)
            
            # Also check for specific title elements
            if not title_link:
                title_elem = article_elem.find(['h2', 'h3', 'h4'])
                if title_elem:
                    title_link = title_elem.find('a', href=True)
            
            if not title_link:
                continue
            
            title = title_link.get_text(strip=True)
            href = title_link.get('href', '')
            
            if not title or not href or len(title) < 10:
                continue
            
            # Skip non-HTTP(S) links (tel:, mailto:, javascript:, etc.)
            if href.startswith(('tel:', 'mailto:', 'javascript:', '#')):
                continue
            
            # Build full URL
            if not href.startswith('http'):
                href = urljoin(base_url, href)
            
            # Final validation - ensure it's a valid HTTP(S) URL
            if not href.startswith(('http://', 'https://')):
                continue
            
            # Try to extract date from WordPress time element
            published_at = None
            time_elem = article_elem.find('time')
            if time_elem:
                datetime_attr = time_elem.get('datetime')
                if datetime_attr:
                    published_at = self._parse_date(datetime_attr)
            
            # Fallback: try to find date in text
            if not published_at:
                date_elem = article_elem.find(class_=lambda c: c and 'date' in c.lower() if c else False)
                if date_elem:
                    published_at = self._parse_date(date_elem.get_text())
            
            items.append({
                'url': href,
                'title': title,
                'published_at': published_at
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
        Extract the main text content from a WordPress article page.
        Uses shared content extraction utility for consistency.
        """
        # Use shared utility with WordPress-specific selectors
        selectors = [
            '.entry-content',
            'article .content',
            '.post-content',
            'article',
            'main',
            '.main-content',
            '.content'
        ]
        
        return extract_main_content(soup, selectors)
