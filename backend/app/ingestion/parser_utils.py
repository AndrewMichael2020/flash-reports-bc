"""
Utilities for parsers: retry logic, error handling, date parsing.
"""
import time
import httpx
from typing import Optional, Callable, TypeVar, Any
from datetime import datetime
from dateutil import parser as date_parser
import re

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry logic."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base


async def retry_with_backoff(
    func: Callable[[], Any],
    config: Optional[RetryConfig] = None,
    retryable_errors: tuple = (httpx.HTTPError, httpx.TimeoutException)
) -> Any:
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        func: Async function to execute
        config: Retry configuration
        retryable_errors: Tuple of exception types to retry on
    
    Returns:
        Result of the function
    
    Raises:
        Last exception if all retries fail
    """
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except retryable_errors as e:
            last_exception = e
            
            if attempt < config.max_retries:
                # Calculate delay with exponential backoff
                delay = min(
                    config.initial_delay * (config.exponential_base ** attempt),
                    config.max_delay
                )
                
                print(f"Retry attempt {attempt + 1}/{config.max_retries} after {delay:.1f}s: {e}")
                time.sleep(delay)
            else:
                print(f"All {config.max_retries} retries exhausted")
    
    if last_exception:
        raise last_exception
    
    # Should never reach here, but just in case
    raise RuntimeError("Retry logic failed without exception")


def parse_flexible_date(text: str) -> Optional[datetime]:
    """
    Parse dates from various common formats.
    
    Handles:
    - ISO format: 2024-01-15, 2024-01-15T10:30:00
    - Month day year: January 15, 2024 / Jan 15, 2024
    - Day month year: 15 January 2024
    - Relative: Today, Yesterday
    - WordPress format: <time datetime="...">
    
    Args:
        text: Text containing a date
    
    Returns:
        Parsed datetime or None if no date found
    """
    if not text:
        return None
    
    # Common date patterns (most specific to least specific)
    patterns = [
        # ISO datetime with timezone
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}',
        # ISO datetime
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        # ISO date
        r'\d{4}-\d{2}-\d{2}',
        # Month day, year (January 15, 2024)
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
        # Short month day, year (Jan 15, 2024)
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}',
        # Day month year (15 January 2024)
        r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
        # Numeric: MM/DD/YYYY or DD/MM/YYYY
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return date_parser.parse(match.group(0), fuzzy=False)
            except (ValueError, TypeError):
                # Try next pattern
                continue
    
    # Try dateutil's fuzzy parsing as last resort
    try:
        return date_parser.parse(text, fuzzy=True)
    except (ValueError, TypeError):
        pass
    
    return None


def extract_wordpress_datetime(soup) -> Optional[datetime]:
    """
    Extract datetime from WordPress <time> tag.
    
    WordPress often uses: <time datetime="2024-01-15T10:30:00+00:00">
    """
    time_tag = soup.find('time')
    if time_tag and time_tag.get('datetime'):
        try:
            return date_parser.parse(time_tag['datetime'])
        except (ValueError, TypeError):
            pass
    
    return None


def clean_html_text(text: str) -> str:
    """
    Clean up text extracted from HTML.
    
    - Removes excessive whitespace
    - Normalizes line breaks
    - Removes special characters that don't render well
    """
    if not text:
        return ""
    
    # Normalize line breaks
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Max 2 consecutive newlines
    
    # Clean up spaces
    text = re.sub(r' +', ' ', text)  # Multiple spaces to single space
    text = re.sub(r'\t+', ' ', text)  # Tabs to space
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Remove special Unicode characters that don't render well
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e]', '', text)  # Zero-width chars
    
    return text.strip()


def extract_main_content(soup, selectors: list) -> Optional[str]:
    """
    Extract main content from HTML using a prioritized list of CSS selectors.
    
    Args:
        soup: BeautifulSoup object
        selectors: List of CSS selectors to try, in priority order
    
    Returns:
        Extracted and cleaned text, or None if no content found
    """
    # Remove unwanted elements
    for unwanted in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
        unwanted.decompose()
    
    # Try each selector
    for selector in selectors:
        content = soup.select_one(selector)
        if content:
            text = content.get_text(separator='\n', strip=True)
            cleaned = clean_html_text(text)
            
            # Only return if we got substantial content
            if len(cleaned) > 100:
                return cleaned
    
    # Fallback: get all text from body
    body = soup.find('body')
    if body:
        text = body.get_text(separator='\n', strip=True)
        return clean_html_text(text)
    
    return None
