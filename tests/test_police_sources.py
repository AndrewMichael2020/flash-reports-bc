#!/usr/bin/env python3
"""
Basic tests for police_sources.py

These tests verify core functionality without requiring a full test framework.
"""

import sys
from pathlib import Path

# Add parent directory to path to import police_sources
sys.path.insert(0, str(Path(__file__).parent.parent))

from police_sources import (
    Agency,
    SourceEndpoint,
    classify_url,
    generate_markdown_tree,
    normalize_url,
)


def test_classify_url():
    """Test URL classification logic."""
    # RSS feeds
    assert classify_url("https://example.com/feed.xml") == "RSS_NATIVE"
    assert classify_url("https://example.com/rss") == "RSS_NATIVE"
    assert classify_url("https://example.com/feed/") == "RSS_NATIVE"
    
    # Social media
    assert classify_url("https://facebook.com/page") == "SOCIAL_PRIMARY"
    assert classify_url("https://twitter.com/account") == "SOCIAL_PRIMARY"
    assert classify_url("https://x.com/account") == "SOCIAL_PRIMARY"
    
    # JSON API
    assert classify_url("https://example.com/api/news") == "JSON_API"
    assert classify_url("https://example.com/data.json") == "JSON_API"
    
    # HTML (default)
    assert classify_url("https://example.com/news") == "HTML_PAGER"
    
    print("✓ test_classify_url passed")


def test_normalize_url():
    """Test URL normalization."""
    base = "https://example.com/path/"
    
    # Relative URLs
    assert normalize_url(base, "news") == "https://example.com/path/news"
    assert normalize_url(base, "../news") == "https://example.com/news"
    assert normalize_url(base, "/news") == "https://example.com/news"
    
    # Absolute URLs
    assert normalize_url(base, "https://other.com/news") == "https://other.com/news"
    
    print("✓ test_normalize_url passed")


def test_markdown_tree_generator():
    """Test that the Markdown tree generator produces valid output."""
    # Create stub agencies
    agencies = [
        Agency(
            name="Test Police Department",
            jurisdiction="BC",
            category="Municipal Police",
            base_url="https://test.example.com",
            endpoints=[
                SourceEndpoint(
                    kind="HTML_PAGER",
                    label="News",
                    url="https://test.example.com/news",
                    http_status=200,
                    is_working=True
                ),
                SourceEndpoint(
                    kind="RSS_NATIVE",
                    label="RSS Feed",
                    url="https://test.example.com/feed.xml",
                    http_status=200,
                    is_working=True
                ),
            ]
        ),
        Agency(
            name="Another Agency",
            jurisdiction="AB",
            category="RCMP",
            base_url="https://another.example.com",
            endpoints=[
                SourceEndpoint(
                    kind="HTML_PAGER",
                    label="Media Releases",
                    url="https://another.example.com/media",
                    http_status=404,
                    is_working=False
                ),
            ]
        ),
    ]
    
    # Test without broken endpoints
    markdown = generate_markdown_tree(agencies, include_broken=False)
    
    # Verify basic structure
    assert "# Police News Source Tree" in markdown
    assert "## BC" in markdown
    assert "## AB" in markdown
    assert "Test Police Department" in markdown
    assert "https://test.example.com/news" in markdown
    assert "https://test.example.com/feed.xml" in markdown
    
    # Broken endpoint should not be included
    assert "https://another.example.com/media" not in markdown
    
    # Test with broken endpoints
    markdown_with_broken = generate_markdown_tree(agencies, include_broken=True)
    assert "https://another.example.com/media" in markdown_with_broken
    assert "BROKEN" in markdown_with_broken
    
    print("✓ test_markdown_tree_generator passed")


def test_agency_dataclass():
    """Test Agency data model."""
    agency = Agency(
        name="Test Agency",
        jurisdiction="WA",
        category="Sheriff",
        base_url="https://test.com"
    )
    
    assert agency.name == "Test Agency"
    assert agency.jurisdiction == "WA"
    assert agency.category == "Sheriff"
    assert agency.base_url == "https://test.com"
    assert agency.endpoints == []
    
    # Add endpoint
    endpoint = SourceEndpoint(
        kind="HTML_PAGER",
        label="News",
        url="https://test.com/news"
    )
    agency.endpoints.append(endpoint)
    
    assert len(agency.endpoints) == 1
    assert agency.endpoints[0].url == "https://test.com/news"
    
    print("✓ test_agency_dataclass passed")


if __name__ == "__main__":
    print("Running tests...\n")
    
    try:
        test_classify_url()
        test_normalize_url()
        test_markdown_tree_generator()
        test_agency_dataclass()
        
        print("\n✅ All tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
