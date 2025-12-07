#!/usr/bin/env python3
"""
Standalone RCMP News Parser Test

This script parses RCMP detachment news pages (e.g., https://rcmp.ca/en/bc/langley/news)
and extracts news articles with their full text and links using Playwright browser automation.

Dependencies:
    - playwright (pip install playwright)
    - beautifulsoup4 (pip install beautifulsoup4)
    
    After installing: playwright install chromium

Usage:
    # Parse RCMP news from default Langley detachment:
    python test_rcmp_news_parsing.py
    
    # Parse from a different RCMP detachment:
    python test_rcmp_news_parsing.py --url "https://rcmp.ca/en/bc/surrey/news"
    
    # Customize output file and article limit:
    python test_rcmp_news_parsing.py --max 5 --output my_news.json

Output:
    A JSON file (rcmp_news_output.json) containing a list of news articles with:
    - title: Article headline
    - url: Full URL to the article
    - published_date: Publication date (if available)
    - body: Full text content of the article

Why Playwright?
    - RCMP websites use JavaScript rendering
    - Playwright handles dynamic content reliably
    - Explicitly allowed per RCMP's robots.txt
    - Most robust solution for modern web scraping

Parsing Strategies:
    The parser tries multiple extraction strategies for robustness:
    - Looks for <article> tags and news listing patterns
    - Checks for links containing "/news/" with dates
    - Extracts dates from <time> tags or date patterns
    - Filters out navigation and non-article links
    - Uses multiple fallback content selectors

Example Output Format:
    {
      "source": "https://rcmp.ca/en/bc/langley/news",
      "fetched_at": "2025-12-07T21:39:56.050061",
      "article_count": 2,
      "articles": [
        {
          "title": "Langley RCMP investigating pedestrian involved collision",
          "url": "https://rcmp.ca/en/bc/langley/news/2025/11/4348078",
          "published_date": "November 29, 2025",
          "body": "News release\\n\\nLangley RCMP investigating..."
        }
      ]
    }

Author: Automated test for RCMP news parsing
Date: 2025-12-07
"""

import json
import asyncio
import re
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("ERROR: Playwright not installed.")
    print("Install with: pip install playwright && playwright install chromium")
    sys.exit(1)


class RCMPNewsParser:
    """
    Parser for RCMP news pages using Playwright browser automation.
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize the parser.
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.base_url = "https://rcmp.ca"
        
    def _extract_articles_from_soup(self, soup: BeautifulSoup, listing_url: str) -> List[Dict[str, str]]:
        """
        Extract article links from parsed HTML (common logic for all methods).
        
        Args:
            soup: BeautifulSoup object
            listing_url: URL of the listing page
            
        Returns:
            List of article metadata dictionaries
        """
        articles = []
        
        # Strategy 1: Look for links in common RCMP news structures
        for article_tag in soup.find_all(['article', 'li', 'div'], class_=lambda x: x and ('news' in str(x).lower() or 'article' in str(x).lower() or 'item' in str(x).lower())):
            link = article_tag.find('a', href=True)
            if link:
                href = link.get('href', '')
                title = link.get_text(strip=True)
                
                # Skip navigation and non-article links
                if len(title) < 20 or any(skip in title.lower() for skip in ['home', 'contact', 'about', 'search', 'menu', 'privacy', 'terms']):
                    continue
                
                # Build full URL
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = self.base_url + href
                else:
                    continue
                
                # Skip if it's the listing page itself
                if full_url == listing_url or full_url.rstrip('/') == listing_url.rstrip('/'):
                    continue
                
                # Try to extract date
                date_str = None
                time_elem = article_tag.find('time')
                if time_elem:
                    date_str = time_elem.get('datetime') or time_elem.get_text(strip=True)
                else:
                    # Look for date patterns in text
                    text = article_tag.get_text()
                    date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}', text)
                    if date_match:
                        date_str = date_match.group(0)
                
                articles.append({
                    'title': title,
                    'url': full_url,
                    'date_str': date_str
                })
        
        # Strategy 2: If no articles found, look for all links with "news" in href
        if not articles:
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                # Look for news article patterns
                if '/news/' in href and any(char.isdigit() for char in href):
                    title = link.get_text(strip=True)
                    
                    if len(title) < 20:
                        # Try to find a heading near this link
                        parent = link.find_parent(['article', 'div', 'li'])
                        if parent:
                            heading = parent.find(['h1', 'h2', 'h3', 'h4'])
                            if heading:
                                title = heading.get_text(strip=True)
                    
                    if len(title) < 20:
                        continue
                    
                    # Build full URL
                    if href.startswith('http'):
                        full_url = href
                    elif href.startswith('/'):
                        full_url = self.base_url + href
                    else:
                        continue
                    
                    articles.append({
                        'title': title,
                        'url': full_url,
                        'date_str': None
                    })
        
        # Remove duplicates
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        return unique_articles
    
    def _extract_article_content(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract main article content from parsed HTML (common logic).
        
        Args:
            soup: BeautifulSoup object of article page
            
        Returns:
            Extracted text content
        """
        # Remove unwanted elements
        for unwanted in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'button', 'iframe']):
            unwanted.decompose()
        
        # Extract main content - try multiple strategies
        article_content = None
        
        # Strategy 1: Look for <article> tag
        article_elem = soup.find('article')
        if article_elem:
            article_content = article_elem.get_text(separator='\n', strip=True)
        
        # Strategy 2: Look for main content area
        if not article_content or len(article_content) < 200:
            main_elem = soup.find('main') or soup.find(id='main') or soup.find(class_=lambda x: x and 'main' in str(x).lower())
            if main_elem:
                article_content = main_elem.get_text(separator='\n', strip=True)
        
        # Strategy 3: Look for content div
        if not article_content or len(article_content) < 200:
            content_elem = soup.find(class_=lambda x: x and ('content' in str(x).lower() or 'article' in str(x).lower()))
            if content_elem:
                article_content = content_elem.get_text(separator='\n', strip=True)
        
        # Strategy 4: Fallback to body
        if not article_content or len(article_content) < 200:
            body_elem = soup.find('body')
            if body_elem:
                article_content = body_elem.get_text(separator='\n', strip=True)
        
        # Clean up the content
        if article_content:
            # Remove excessive whitespace
            article_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', article_content)
            article_content = re.sub(r' +', ' ', article_content)
            article_content = article_content.strip()
        
        return article_content
        
    async def parse_listing_page(self, page: Page, listing_url: str) -> List[Dict[str, str]]:
        """
        Parse the news listing page to extract article links using Playwright.
        
        Args:
            page: Playwright page object
            listing_url: URL of the news listing page
            
        Returns:
            List of dictionaries with article metadata
        """
        print(f"Fetching listing page: {listing_url}")
        
        try:
            # Navigate to the listing page
            await page.goto(listing_url, wait_until="networkidle", timeout=30000)
            
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Get the page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Use common extraction logic
            articles = self._extract_articles_from_soup(soup, listing_url)
            
            print(f"Found {len(articles)} unique articles")
            return articles
            
        except Exception as e:
            print(f"Error parsing listing page: {e}")
            return []
    
    async def parse_article_page(self, page: Page, article_url: str) -> Optional[str]:
        """
        Parse an individual article page to extract full content using Playwright.
        
        Args:
            page: Playwright page object
            article_url: URL of the article
            
        Returns:
            Full text content of the article
        """
        try:
            print(f"Fetching article: {article_url}")
            
            # Navigate to article page
            await page.goto(article_url, wait_until="networkidle", timeout=30000)
            
            # Wait for content
            await page.wait_for_timeout(1500)
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Use common extraction logic
            return self._extract_article_content(soup)
            
        except Exception as e:
            print(f"Error parsing article page {article_url}: {e}")
            return None
    
    async def fetch_all_news(self, listing_url: str, max_articles: int = 10) -> List[Dict[str, any]]:
        """
        Fetch all news articles from a listing page using Playwright browser automation.
        
        Args:
            listing_url: URL of the news listing page
            max_articles: Maximum number of articles to fetch
            
        Returns:
            List of dictionaries with article data
        """
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            try:
                # Get article links from listing page
                articles_metadata = await self.parse_listing_page(page, listing_url)
                
                # Limit articles
                articles_metadata = articles_metadata[:max_articles]
                
                # Fetch each article's content
                results = []
                for i, metadata in enumerate(articles_metadata, 1):
                    print(f"\nProcessing article {i}/{len(articles_metadata)}")
                    
                    body = await self.parse_article_page(page, metadata['url'])
                    
                    if body:
                        results.append({
                            'title': metadata['title'],
                            'url': metadata['url'],
                            'published_date': metadata.get('date_str'),
                            'body': body
                        })
                    
                    # Be nice to the server
                    await asyncio.sleep(1)
                
                return results
                
            finally:
                await browser.close()


async def main():
    """
    Main function to run the RCMP news parser.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='RCMP News Parser - Standalone Test')
    parser.add_argument('--url', type=str, default='https://rcmp.ca/en/bc/langley/news',
                      help='URL of the RCMP news listing page')
    parser.add_argument('--max', type=int, default=10,
                      help='Maximum number of articles to fetch')
    parser.add_argument('--output', type=str, default='tests/rcmp_news_output.json',
                      help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Configuration
    LISTING_URL = args.url
    OUTPUT_FILE = args.output
    MAX_ARTICLES = args.max
    
    print("=" * 80)
    print("RCMP News Parser - Standalone Test (Playwright)")
    print("=" * 80)
    print(f"\nTarget URL: {LISTING_URL}")
    print(f"Max articles to fetch: {MAX_ARTICLES}")
    print(f"Output file: {OUTPUT_FILE}\n")
    
    # Create parser
    news_parser = RCMPNewsParser(headless=True)
    
    # Fetch news
    try:
        articles = await news_parser.fetch_all_news(LISTING_URL, max_articles=MAX_ARTICLES)
        
        # Save to JSON
        output_data = {
            'source': LISTING_URL,
            'fetched_at': datetime.now().isoformat(),
            'article_count': len(articles),
            'articles': articles
        }
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'=' * 80}")
        print(f"SUCCESS: Fetched {len(articles)} articles")
        print(f"Output saved to: {OUTPUT_FILE}")
        print(f"{'=' * 80}\n")
        
        # Print summary
        if articles:
            print("Article Summary:")
            print("-" * 80)
            for i, article in enumerate(articles, 1):
                print(f"{i}. {article['title'][:70]}")
                print(f"   URL: {article['url']}")
                print(f"   Date: {article.get('published_date', 'N/A')}")
                print(f"   Content length: {len(article['body'])} characters")
                print()
            
            # Show example output for first article
            print("=" * 80)
            print("EXAMPLE OUTPUT (First Article):")
            print("=" * 80)
            print(json.dumps(articles[0], indent=2, ensure_ascii=False))
            print()
        else:
            print("\nNo articles were fetched. Check the URL and network connection.")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
