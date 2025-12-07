"""
WordPress Parser.
Handles WordPress-based police newsroom sites (e.g., VPD).
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
                # Fetch the newsroom listing page
                response = await client.get(base_url, follow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find news items (WordPress typically uses article tags or post classes)
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
            print(f"Error fetching WordPress articles: {e}")
            
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
        """
        if not text:
            return None
        
        try:
            # Try ISO format first (WordPress datetime attribute)
            if 'T' in text and ('-' in text or ':' in text):
                return date_parser.parse(text)
            
            # Look for date patterns
            date_patterns = [
                r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
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
        Extract the main text content from a WordPress article page.
        """
        # Remove unwanted elements
        for unwanted in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
            unwanted.decompose()
        
        # WordPress commonly uses these content selectors
        content = None
        for selector in [
            '.entry-content',
            'article .content',
            '.post-content',
            'article',
            'main',
            '.main-content'
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
