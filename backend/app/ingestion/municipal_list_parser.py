"""
Municipal List Parser.
Handles municipal police newsroom sites with list-style layouts (e.g., Surrey PD, Abbotsford PD).
"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List
import hashlib
import re
from urllib.parse import urljoin
from dateutil import parser as date_parser
from app.ingestion.parser_base import SourceParser, RawArticle


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
                # Fetch the newsroom listing page
                response = await client.get(base_url, follow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find news items
                news_items = self._extract_news_items(soup, base_url)
                
                for item in news_items:
                    # Check if we should stop based on date
                    if since and item['published_at'] and item['published_at'] <= since:
                        break
                    
                    # Fetch the full article
                    article = await self._fetch_article_detail(client, item)
                    if article:
                        articles.append(article)
                 
        except Exception as e:
            print(f"Error fetching municipal articles: {e}")
            
        return articles
    
    def _extract_news_items(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        """
        Extract news items from municipal list/card layout.
        Returns list of dicts with url, title, published_at.
        """
        items = []
        
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
        
        return items
    
    def _parse_date(self, text: str) -> Optional[datetime]:
        """
        Attempt to parse a date from text.
        """
        if not text:
            return None
        
        try:
            # Try ISO format first
            if 'T' in text and ('-' in text or ':' in text):
                return date_parser.parse(text)
            
            # Look for date patterns
            date_patterns = [
                r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
                r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY or DD/MM/YYYY
                r'\w+ \d{1,2},? \d{4}',  # Month DD, YYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
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
            print(f"Error fetching article detail from {item['url']}: {e}")
            return None
    
    def _extract_body(self, soup: BeautifulSoup) -> str:
        """
        Extract the main text content from an article page.
        """
        # Remove unwanted elements
        for unwanted in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
            unwanted.decompose()
        
        # Try common content selectors
        content = None
        for selector in [
            '.content',
            '#content',
            'article',
            'main',
            '.main-content',
            '.news-content',
            '.release-content'
        ]:
            content = soup.select_one(selector)
            if content:
                break
        
        if not content:
            # Fallback to body
            content = soup.find('body')
        
        if content:
            # Get text with cleanup
            text = content.get_text(separator='\n', strip=True)
            # Clean up excessive whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = re.sub(r' +', ' ', text)
            return text
        
        return ""
