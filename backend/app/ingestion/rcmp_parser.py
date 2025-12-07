"""
RCMP Newsroom Parser.
Handles parsing of RCMP detachment newsroom pages.

Example URL: https://rcmp.ca/en/bc/langley/news
"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List
import hashlib
import logging
from urllib.parse import urljoin, urlparse
from app.ingestion.parser_base import SourceParser, RawArticle
from app.ingestion.parser_utils import (
    retry_with_backoff, 
    RetryConfig,
    parse_flexible_date,
    extract_main_content
)

logger = logging.getLogger(__name__)


class RCMPParser(SourceParser):
    """Parser for RCMP detachment newsrooms."""
    
    def __init__(self):
        self.retry_config = RetryConfig(max_retries=3, initial_delay=1.0)
    
    async def fetch_new_articles(
        self,
        source_id: int,
        base_url: str,
        since: Optional[datetime] = None
    ) -> List[RawArticle]:
        """
        Fetch new articles from an RCMP newsroom.
        
        Supports the new rcmp.ca/en/{province}/{detachment}/news URL structure.
        """
        articles = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # Fetch the newsroom listing page with retry
                async def fetch_listing():
                    response = await client.get(base_url)
                    response.raise_for_status()
                    return response
                
                response = await retry_with_backoff(fetch_listing, self.retry_config)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract news items from the listing
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
            logger.error(f"Error fetching RCMP articles from {base_url}: {e}")
            
        return articles
    
    def _extract_news_items(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        """
        Extract news items from the RCMP newsroom listing page.
        
        RCMP pages typically have news releases in a list or card format.
        This implementation looks for common patterns across different RCMP detachments.
        """
        items = []
        
        # Parse base URL for constructing absolute URLs
        parsed_base = urlparse(base_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
        
        # Look for news article links
        # RCMP sites use various structures; try multiple approaches
        
        # Approach 1: Look for links containing "news" or article-like hrefs
        potential_links = []
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Skip if no meaningful text
            if not text or len(text) < 15:
                continue
            
            # Skip non-HTTP(S) links (tel:, mailto:, javascript:, etc.)
            if href.startswith(('tel:', 'mailto:', 'javascript:', '#')):
                continue
            
            # Look for news-related URLs
            if any(keyword in href.lower() for keyword in ['news', 'media-centre', 'release', 'article']):
                potential_links.append((link, href, text))
            # Also check if the link parent looks like a news item container
            elif link.find_parent(['article', 'li']) and len(text) > 20:
                potential_links.append((link, href, text))
        
        for link, href, title in potential_links:
            # Build full URL
            full_url = urljoin(base_url, href)
            
            # Final validation - ensure it's a valid HTTP(S) URL
            if not full_url.startswith(('http://', 'https://')):
                continue
            
            # Skip if it's just the news index page
            if full_url == base_url:
                continue
            
            # Try to extract date from surrounding context
            published_at = None
            
            # Look in parent elements for date
            parent = link.find_parent(['article', 'li', 'div'])
            if parent:
                parent_text = parent.get_text()
                published_at = parse_flexible_date(parent_text)
            
            # Also check for time elements
            if not published_at:
                time_elem = link.find_parent().find('time') if link.find_parent() else None
                if time_elem:
                    time_text = time_elem.get('datetime') or time_elem.get_text()
                    published_at = parse_flexible_date(time_text)
            
            items.append({
                'url': full_url,
                'title': title,
                'published_at': published_at
            })
        
        # Remove duplicates by URL
        seen_urls = set()
        unique_items = []
        for item in items:
            if item['url'] not in seen_urls:
                seen_urls.add(item['url'])
                unique_items.append(item)
        
        # Limit to most recent items
        return unique_items[:15]
    
    async def _fetch_article_detail(
        self,
        client: httpx.AsyncClient,
        item: dict
    ) -> Optional[RawArticle]:
        """
        Fetch the full content of an article from its detail page with retry logic.
        """
        try:
            async def fetch_detail():
                response = await client.get(item['url'])
                response.raise_for_status()
                return response
            
            response = await retry_with_backoff(fetch_detail, self.retry_config)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract main content using prioritized selectors
            selectors = [
                'article',
                'main',
                '.article-content',
                '.content',
                '#content',
                '.news-content',
                '[role="main"]'
            ]
            
            body_raw = extract_main_content(soup, selectors)
            
            if not body_raw or len(body_raw) < 50:
                logger.warning(f"No substantial content found for {item['url']}")
                return None
            
            # Try to extract a better date if we didn't get one from the listing
            if not item.get('published_at'):
                # Look for time element in article
                time_elem = soup.find('time')
                if time_elem:
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        item['published_at'] = parse_flexible_date(datetime_attr)
                    else:
                        item['published_at'] = parse_flexible_date(time_elem.get_text())
                
                # Fallback: search entire text
                if not item['published_at']:
                    item['published_at'] = parse_flexible_date(body_raw[:500])
            
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
                raw_html=response.text[:10000]  # Store first 10k chars of HTML
            )
            
        except Exception as e:
            logger.error(f"Error fetching article detail from {item['url']}: {e}")
            return None
