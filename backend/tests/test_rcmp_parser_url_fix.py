"""
Test for RCMP parser URL resolution fix.
Validates that relative URLs are resolved using the listing_url instead of hardcoded base_url.
"""
import pytest
from bs4 import BeautifulSoup
from app.ingestion.rcmp_parser import RCMPParser


class TestRCMPParserURLResolution:
    """Test RCMP parser URL resolution for different agencies."""

    def test_abbotsford_relative_url_resolution(self):
        """Test that Abbotsford PD relative URLs are resolved correctly."""
        parser = RCMPParser(use_playwright=False)
        
        # Mock HTML from Abbotsford PD with relative links
        mock_html = """
        <html>
            <body>
                <div class="news-list">
                    <article class="news-item">
                        <h3><a href="/blog/news_releases/fatal-accident">Fatal Motor Vehicle Accident on Highway 1</a></h3>
                        <time datetime="2024-12-01">December 1, 2024</time>
                    </article>
                    <article class="news-item">
                        <h3><a href="/blog/news_releases/theft-investigation">Theft Investigation Ongoing</a></h3>
                        <time datetime="2024-12-02">December 2, 2024</time>
                    </article>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(mock_html, 'html.parser')
        listing_url = "https://www.abbypd.ca/blog/news_releases"
        
        articles = parser._extract_articles_from_soup(soup, listing_url)
        
        # Should extract 2 articles
        assert len(articles) == 2
        
        # URLs should be resolved relative to abbypd.ca, not rcmp.ca
        assert articles[0]['url'] == "https://www.abbypd.ca/blog/news_releases/fatal-accident"
        assert articles[1]['url'] == "https://www.abbypd.ca/blog/news_releases/theft-investigation"
        
        # Titles should be extracted
        assert "Fatal Motor Vehicle Accident" in articles[0]['title']
        assert "Theft Investigation" in articles[1]['title']

    def test_surrey_relative_url_resolution(self):
        """Test that Surrey Police relative URLs are resolved correctly (old pattern)."""
        parser = RCMPParser(use_playwright=False)
        
        # Mock HTML from Surrey Police with relative links (old pattern)
        mock_html = """
        <html>
            <body>
                <div class="news-list">
                    <article class="news-item">
                        <h3><a href="/news-events/news/armed-robbery-investigation">Armed Robbery Investigation in Progress</a></h3>
                        <time datetime="2024-12-01">December 1, 2024</time>
                    </article>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(mock_html, 'html.parser')
        listing_url = "https://surreypolice.ca/news-events/news"
        
        articles = parser._extract_articles_from_soup(soup, listing_url)
        
        # Should extract 1 article
        assert len(articles) == 1
        
        # URL should be resolved relative to surreypolice.ca, not rcmp.ca
        assert articles[0]['url'] == "https://surreypolice.ca/news-events/news/armed-robbery-investigation"
        
        # Title should be extracted
        assert "Armed Robbery Investigation" in articles[0]['title']

    def test_surrey_new_pattern_url_resolution(self):
        """Test that Surrey Police new /news-releases/ pattern URLs are resolved correctly."""
        parser = RCMPParser(use_playwright=False)
        
        # Mock HTML from Surrey Police with relative links (new pattern)
        mock_html = """
        <html>
            <body>
                <div class="news-list">
                    <article class="news-item">
                        <h3><a href="/news-releases/suspect-arrested-following-robbery">Suspect Arrested Following Armed Robbery Investigation</a></h3>
                        <time datetime="2024-12-01">December 1, 2024</time>
                    </article>
                    <article class="news-item">
                        <h3><a href="/news-releases/vehicle-pursuit-ends-in-arrest">Vehicle Pursuit Ends in Arrest on Highway 1</a></h3>
                        <time datetime="2024-12-02">December 2, 2024</time>
                    </article>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(mock_html, 'html.parser')
        listing_url = "https://www.surreypolice.ca/news-releases"
        
        articles = parser._extract_articles_from_soup(soup, listing_url)
        
        # Should extract 2 articles
        assert len(articles) == 2
        
        # URLs should be resolved relative to surreypolice.ca, not rcmp.ca
        assert articles[0]['url'] == "https://www.surreypolice.ca/news-releases/suspect-arrested-following-robbery"
        assert articles[1]['url'] == "https://www.surreypolice.ca/news-releases/vehicle-pursuit-ends-in-arrest"
        
        # Titles should be extracted
        assert "Suspect Arrested" in articles[0]['title']
        assert "Vehicle Pursuit" in articles[1]['title']

    def test_rcmp_still_works(self):
        """Test that RCMP news (with digits) still works correctly."""
        parser = RCMPParser(use_playwright=False)
        
        # Mock HTML from RCMP with their typical URL structure
        mock_html = """
        <html>
            <body>
                <div class="news-list">
                    <article class="news-item">
                        <h3><a href="/en/bc/langley/news/2024/11/4348078">Langley RCMP investigating pedestrian collision</a></h3>
                        <time datetime="2024-11-29">November 29, 2024</time>
                    </article>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(mock_html, 'html.parser')
        listing_url = "https://rcmp.ca/en/bc/langley/news"
        
        articles = parser._extract_articles_from_soup(soup, listing_url)
        
        # Should extract 1 article
        assert len(articles) == 1
        
        # URL should be resolved relative to the listing URL
        assert articles[0]['url'] == "https://rcmp.ca/en/bc/langley/news/2024/11/4348078"
        
        # Title should be extracted
        assert "Langley RCMP" in articles[0]['title']

    def test_bad_titles_filtered(self):
        """Test that noise links like 'Proactive Disclosure' are filtered out."""
        parser = RCMPParser(use_playwright=False)
        
        # Mock HTML with utility/navigation links that should be filtered
        mock_html = """
        <html>
            <body>
                <div class="news-list">
                    <article class="news-item">
                        <h3><a href="/proactive-disclosure">Proactive Disclosure</a></h3>
                    </article>
                    <article class="news-item">
                        <h3><a href="/headquarters-update">Headquarters Update</a></h3>
                    </article>
                    <article class="news-item">
                        <h3><a href="/blog/news_releases/valid-news-article">Valid News Article About Crime Investigation</a></h3>
                        <time datetime="2024-12-01">December 1, 2024</time>
                    </article>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(mock_html, 'html.parser')
        listing_url = "https://www.abbypd.ca/blog/news_releases"
        
        articles = parser._extract_articles_from_soup(soup, listing_url)
        
        # Should only extract the valid news article (not the utility links)
        assert len(articles) == 1
        assert "Valid News Article" in articles[0]['title']
        
        # Verify noise is filtered out
        titles = [a['title'].lower() for a in articles]
        assert not any('proactive disclosure' in t for t in titles)
        assert not any('headquarters update' in t for t in titles)

    def test_absolute_urls_unchanged(self):
        """Test that absolute URLs are not modified."""
        parser = RCMPParser(use_playwright=False)
        
        # Mock HTML with absolute URLs
        mock_html = """
        <html>
            <body>
                <div class="news-list">
                    <article class="news-item">
                        <h3><a href="https://www.abbypd.ca/blog/news_releases/absolute-url-test">Article with Absolute URL</a></h3>
                        <time datetime="2024-12-01">December 1, 2024</time>
                    </article>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(mock_html, 'html.parser')
        listing_url = "https://www.abbypd.ca/blog/news_releases"
        
        articles = parser._extract_articles_from_soup(soup, listing_url)
        
        # Should extract 1 article
        assert len(articles) == 1
        
        # Absolute URL should remain unchanged
        assert articles[0]['url'] == "https://www.abbypd.ca/blog/news_releases/absolute-url-test"
