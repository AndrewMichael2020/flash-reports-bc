"""
Parser interface and base implementation.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class RawArticle:
    """Represents a raw article extracted from a source."""
    external_id: str
    url: str
    title_raw: str
    published_at: Optional[datetime]
    body_raw: str
    raw_html: Optional[str] = None


class SourceParser(ABC):
    """
    Abstract base class for source parsers.
    Each parser implements fetching and parsing logic for a specific source type.
    """
    
    @abstractmethod
    async def fetch_new_articles(
        self, 
        source_id: int,
        base_url: str, 
        since: Optional[datetime] = None
    ) -> List[RawArticle]:
        """
        Fetch new articles from the source.
        
        Args:
            source_id: Database ID of the source
            base_url: Base URL of the newsroom
            since: Only fetch articles newer than this timestamp
            
        Returns:
            List of RawArticle objects
        """
        pass
