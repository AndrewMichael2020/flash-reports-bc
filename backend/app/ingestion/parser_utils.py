"""
Shared utilities for news parsers.
Provides retry logic, date parsing, content extraction, and text cleaning.
"""
import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Any, List
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0


async def retry_with_backoff(
    func: Callable,
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> Any:
    """
    Execute an async function with exponential backoff retry logic.
    
    Args:
        func: Async function to execute
        config: RetryConfig with retry parameters
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of func
        
    Raises:
        Last exception if all retries exhausted
    """
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    delay = config.initial_delay
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # If this was the last attempt, raise
            if attempt >= config.max_retries:
                raise
            
            # Wait before retrying with exponential backoff
            await asyncio.sleep(delay)
            delay = min(delay * config.backoff_factor, config.max_delay)
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    

def parse_flexible_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string in various formats.
    
    Handles:
    - ISO format (2024-12-01T10:30:00Z)
    - YYYY-MM-DD
    - MM/DD/YYYY and DD/MM/YYYY
    - Month DD, YYYY (December 1, 2024)
    - Mon DD, YYYY (Dec 1, 2024)
    
    Args:
        date_str: Date string to parse
        
    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None
    
    try:
        # Try direct parsing first (handles ISO and many other formats)
        return date_parser.parse(date_str)
    except Exception:
        pass
    
    # Try extracting date patterns from text
    patterns = [
        # ISO format
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        r'\d{4}-\d{2}-\d{2}',
        # US/UK format
        r'\d{1,2}/\d{1,2}/\d{4}',
        # Month name formats
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            try:
                return date_parser.parse(match.group(0))
            except Exception:
                continue
    
    return None


def extract_main_content(
    soup: BeautifulSoup,
    selectors: Optional[List[str]] = None,
    remove_tags: Optional[List[str]] = None
) -> str:
    """
    Extract main content from HTML using selectors.
    
    Args:
        soup: BeautifulSoup object
        selectors: List of CSS selectors to try (in order)
        remove_tags: List of tag names to remove before extraction
        
    Returns:
        Extracted text content
    """
    if selectors is None:
        selectors = [
            'article',
            'main',
            '.content',
            '#content',
            '.main-content',
            '.article-content',
            '.post-content',
            '.entry-content'
        ]
    
    if remove_tags is None:
        remove_tags = [
            'script', 'style', 'nav', 'header', 'footer',
            'aside', 'form', 'button', 'iframe'
        ]
    
    # Remove unwanted elements
    for tag_name in remove_tags:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    
    # Try each selector
    for selector in selectors:
        try:
            if selector.startswith('.') or selector.startswith('#'):
                # CSS selector
                element = soup.select_one(selector)
            else:
                # Tag name
                element = soup.find(selector)
            
            if element:
                text = element.get_text(separator='\n', strip=True)
                if text and len(text) > 100:  # Minimum content length
                    return clean_html_text(text)
        except Exception:
            continue
    
    # Fallback to body
    body = soup.find('body')
    if body:
        return clean_html_text(body.get_text(separator='\n', strip=True))
    
    return ""


def clean_html_text(text: str) -> str:
    """
    Clean up whitespace and formatting in extracted HTML text.
    
    Args:
        text: Raw text extracted from HTML
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Clean up tabs first (replace with spaces)
    text = text.replace('\t', ' ')
    
    # Normalize whitespace
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text
