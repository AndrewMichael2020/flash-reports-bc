"""
RCMP Newsroom Parser.
Handles parsing of RCMP detachment newsroom pages.

Example URL: https://bc-cb.rcmp-grc.gc.ca/ViewPage.action?siteNodeId=2087&languageId=1&contentId=-1
"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List
import hashlib
from app.ingestion.parser_base import SourceParser, RawArticle


class RCMPParser(SourceParser):
    """Parser for RCMP detachment newsrooms."""
    
    async def fetch_new_articles(
        self,
        source_id: int,
        base_url: str,
        since: Optional[datetime] = None
    ) -> List[RawArticle]:
        """
        Fetch new articles from an RCMP newsroom.
        
        For Phase A, implements a basic parser for Langley RCMP.
        The RCMP newsroom typically has a list of news releases with titles,
        dates, and links to detail pages.
        """
        articles = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fetch the newsroom listing page
                response = await client.get(base_url, follow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find news release items
                # RCMP newsrooms typically use a consistent structure
                # This is a simplified parser; real implementation may need adjustment
                news_items = self._extract_news_items(soup)
                
                for item in news_items:
                    # Check if we should stop based on date
                    if since and item['published_at'] and item['published_at'] <= since:
                        break
                    
                    # Fetch the full article
                    article = await self._fetch_article_detail(client, item)
                    if article:
                        articles.append(article)
                
        except Exception as e:
            print(f"Error fetching RCMP articles: {e}")
            
        return articles
    
    def _extract_news_items(self, soup: BeautifulSoup) -> List[dict]:
        """
        Extract news items from the RCMP newsroom listing page.
        Returns list of dicts with url, title, published_at.
        """
        items = []
        
        # RCMP sites often use specific classes or structures
        # This is a generic implementation that looks for common patterns
        
        # Look for news release links
        # Common patterns: div.newsItem, article, or links in a list
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Skip non-news links
            if not href or 'ViewPage' not in href and 'news' not in href.lower():
                continue
                
            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            
            # Build full URL
            if href.startswith('http'):
                full_url = href
            elif href.startswith('/'):
                # Extract base domain from base_url
                from urllib.parse import urlparse
                parsed = urlparse(link.base_uri if hasattr(link, 'base_uri') else soup.find('base')['href'] if soup.find('base') else '')
                base = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ''
                full_url = base + href if base else href
            else:
                full_url = href
            
            # Try to extract date (RCMP often includes dates in the text or metadata)
            date_elem = link.find_parent()
            published_at = None
            if date_elem:
                date_text = date_elem.get_text()
                published_at = self._parse_date(date_text)
            
            items.append({
                'url': full_url,
                'title': title,
                'published_at': published_at
            })
        
        # Limit to most recent items for demo
        return items[:10]
    
    def _parse_date(self, text: str) -> Optional[datetime]:
        """
        Attempt to parse a date from text.
        RCMP dates are often in format like "January 15, 2024" or "2024-01-15"
        """
        import re
        from dateutil import parser as date_parser
        
        # Look for date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\w+ \d{1,2},? \d{4}',  # Month DD, YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return date_parser.parse(match.group(0))
                except:
                    pass
        
        return None
    
    async def _fetch_article_detail(
        self,
        client: httpx.AsyncClient,
        item: dict
    ) -> Optional[RawArticle]:
        """
        Fetch the full content of an article from its detail page.
        """
        try:
            response = await client.get(item['url'], follow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract main content
            # RCMP pages typically have content in specific divs or sections
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
                raw_html=response.text[:10000]  # Store first 10k chars of HTML
            )
            
        except Exception as e:
            print(f"Error fetching article detail from {item['url']}: {e}")
            return None
    
    def _extract_body(self, soup: BeautifulSoup) -> str:
        """
        Extract the main text content from an article page.
        """
        # Remove script and style elements
        for script in soup(['script', 'style', 'nav', 'header', 'footer']):
            script.decompose()
        
        # Look for main content areas
        # Try common content containers
        content = None
        
        for selector in ['article', 'main', '.content', '#content', '.news-content']:
            content = soup.select_one(selector)
            if content:
                break
        
        if not content:
            # Fallback to body
            content = soup.find('body')
        
        if content:
            # Get text with some cleanup
            text = content.get_text(separator='\n', strip=True)
            # Clean up excessive whitespace
            import re
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = re.sub(r' +', ' ', text)
            return text
        
        return ""
