"""
Unit tests for parser utilities.
"""
import pytest
from datetime import datetime
from bs4 import BeautifulSoup
from app.ingestion.parser_utils import (
    parse_flexible_date,
    clean_html_text,
    extract_main_content,
    extract_wordpress_datetime
)


class TestDateParsing:
    """Test flexible date parsing."""
    
    def test_iso_date(self):
        """Test ISO format date parsing."""
        result = parse_flexible_date("2024-01-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
    
    def test_iso_datetime(self):
        """Test ISO datetime parsing."""
        result = parse_flexible_date("2024-01-15T10:30:00")
        assert result is not None
        assert result.year == 2024
        assert result.hour == 10
    
    def test_month_day_year(self):
        """Test 'January 15, 2024' format."""
        result = parse_flexible_date("January 15, 2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
    
    def test_short_month(self):
        """Test 'Jan 15, 2024' format."""
        result = parse_flexible_date("Jan 15, 2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
    
    def test_date_in_context(self):
        """Test extracting date from surrounding text."""
        text = "Posted on January 15, 2024 by Admin"
        result = parse_flexible_date(text)
        assert result is not None
        assert result.year == 2024
    
    def test_invalid_date(self):
        """Test that invalid dates return None."""
        result = parse_flexible_date("Not a date")
        assert result is None
    
    def test_empty_string(self):
        """Test empty string."""
        result = parse_flexible_date("")
        assert result is None


class TestTextCleaning:
    """Test HTML text cleaning."""
    
    def test_clean_whitespace(self):
        """Test whitespace normalization."""
        text = "Hello    world\n\n\n\nTest"
        result = clean_html_text(text)
        assert "    " not in result
        assert "\n\n\n" not in result
    
    def test_clean_line_breaks(self):
        """Test line break normalization."""
        text = "Line 1\r\n\r\nLine 2"
        result = clean_html_text(text)
        assert "\r" not in result
        assert result.count("\n\n") <= 1
    
    def test_trim_lines(self):
        """Test line trimming."""
        text = "  Line 1  \n  Line 2  "
        result = clean_html_text(text)
        assert not result.startswith(" ")
        assert not result.endswith(" ")


class TestContentExtraction:
    """Test main content extraction from HTML."""
    
    def test_extract_from_article_tag(self):
        """Test extracting from <article> tag."""
        html = """
        <html>
            <body>
                <nav>Navigation</nav>
                <article>This is the main content.</article>
                <footer>Footer</footer>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        result = extract_main_content(soup, ['article', 'main'])
        assert result is not None
        assert "main content" in result
        assert "Navigation" not in result
        assert "Footer" not in result
    
    def test_extract_from_main_tag(self):
        """Test extracting from <main> tag."""
        html = """
        <html>
            <body>
                <main>Main content here</main>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        result = extract_main_content(soup, ['article', 'main'])
        assert result is not None
        assert "Main content" in result
    
    def test_selector_priority(self):
        """Test that selectors are tried in order."""
        html = """
        <html>
            <body>
                <article>Article content that is long enough to pass the minimum character requirement for extraction successfully</article>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        # Should match article selector
        result = extract_main_content(soup, ['article', '.content'])
        assert result is not None
        assert "Article content" in result
        assert "long enough" in result
    
    def test_remove_unwanted_elements(self):
        """Test that scripts and styles are removed."""
        html = """
        <html>
            <body>
                <article>
                    Content here
                    <script>alert('test');</script>
                    <style>.test { color: red; }</style>
                </article>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        result = extract_main_content(soup, ['article'])
        assert "Content here" in result
        assert "alert" not in result
        assert "color" not in result


class TestWordPressDateExtraction:
    """Test WordPress time tag extraction."""
    
    def test_extract_from_time_tag(self):
        """Test extracting datetime from <time> tag."""
        html = '<time datetime="2024-01-15T10:30:00+00:00">January 15, 2024</time>'
        soup = BeautifulSoup(html, 'html.parser')
        result = extract_wordpress_datetime(soup)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
    
    def test_no_time_tag(self):
        """Test when no time tag exists."""
        html = '<div>No time tag here</div>'
        soup = BeautifulSoup(html, 'html.parser')
        result = extract_wordpress_datetime(soup)
        assert result is None
