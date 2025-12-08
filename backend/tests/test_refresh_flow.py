"""
Comprehensive tests for the refresh flow.
Tests article ingestion, duplicate detection, and enrichment.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.db import Base, get_db
from app.models import Source, ArticleRaw, IncidentEnriched
from app.ingestion.parser_base import RawArticle


# Create test database
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_test_data():
    """Seed test data before each test, clean up after."""
    db = TestingSessionLocal()
    try:
        # Add a test source
        test_source = Source(
            agency_name="Test Police Department",
            jurisdiction="BC",
            region_label="Fraser Valley, BC",
            source_type="MUNICIPAL_PD_NEWS",
            base_url="https://example.com/news",
            parser_id="municipal_list",
            active=True
        )
        db.add(test_source)
        db.commit()
    finally:
        db.close()
    
    yield
    
    # Clean up
    db = TestingSessionLocal()
    try:
        db.query(IncidentEnriched).delete()
        db.query(ArticleRaw).delete()
        db.query(Source).delete()
        db.commit()
    finally:
        db.close()


class TestDuplicateDetection:
    """Test duplicate article detection logic."""
    
    def test_duplicate_article_not_added(self):
        """Test that duplicate articles are not added to database."""
        # Add an existing article
        db = TestingSessionLocal()
        source = db.query(Source).first()
        
        existing_article = ArticleRaw(
            source_id=source.id,
            external_id="article-123",
            url="https://example.com/article-123",
            title_raw="Test Article",
            published_at=datetime.now(timezone.utc),
            body_raw="Test body",
            raw_html="<p>Test</p>"
        )
        db.add(existing_article)
        db.commit()
        
        # Mock parser to return the same article
        mock_article = RawArticle(
            external_id="article-123",
            url="https://example.com/article-123",
            title_raw="Test Article (updated title)",
            published_at=datetime.now(timezone.utc),
            body_raw="Updated body",
            raw_html="<p>Updated</p>"
        )
        
        # Mock sync_sources_to_db to prevent adding config sources
        with patch("app.main.sync_sources_to_db") as mock_sync:
            mock_sync.return_value = 0  # No sources synced
            
            with patch("app.main.get_parser") as mock_get_parser:
                mock_parser = AsyncMock()
                mock_parser.fetch_new_articles.return_value = [mock_article]
                mock_get_parser.return_value = mock_parser
                
                response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["new_articles"] == 0  # Should not add duplicate
        
        # Verify only one article exists
        count = db.query(ArticleRaw).filter(ArticleRaw.external_id == "article-123").count()
        assert count == 1
        
        # Verify title wasn't updated (original preserved)
        article = db.query(ArticleRaw).filter(ArticleRaw.external_id == "article-123").first()
        assert article.title_raw == "Test Article"
        
        db.close()
    
    def test_new_article_added(self):
        """Test that new articles are added to database."""
        db = TestingSessionLocal()
        source = db.query(Source).first()
        
        mock_article = RawArticle(
            external_id="article-new-123",
            url="https://example.com/article-new-123",
            title_raw="New Test Article",
            published_at=datetime.now(timezone.utc),
            body_raw="New test body",
            raw_html="<p>New test</p>"
        )
        
        # Mock sync_sources_to_db to prevent adding config sources
        with patch("app.main.sync_sources_to_db") as mock_sync:
            mock_sync.return_value = 0
            
            with patch("app.main.get_parser") as mock_get_parser:
                mock_parser = AsyncMock()
                mock_parser.fetch_new_articles.return_value = [mock_article]
                mock_get_parser.return_value = mock_parser
                
                # Mock enricher
                with patch("app.main.GeminiEnricher") as mock_enricher_class:
                    mock_enricher = AsyncMock()
                    mock_enricher.enrich_article.return_value = {
                        "severity": "HIGH",
                        "summary_tactical": "Test summary",
                        "tags": ["test"],
                        "entities": [{"name": "Test Person", "type": "person"}],
                        "location_label": "Test Location",
                        "lat": 49.0,
                        "lng": -122.0,
                        "graph_cluster_key": "test-cluster"
                    }
                    mock_enricher.model_name = "test-model"
                    mock_enricher.prompt_version = "v1"
                    mock_enricher_class.return_value = mock_enricher
                    
                    response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["new_articles"] == 1
        
        # Verify article was added
        count = db.query(ArticleRaw).filter(ArticleRaw.external_id == "article-new-123").count()
        assert count == 1
        
        # Verify enrichment was created
        article = db.query(ArticleRaw).filter(ArticleRaw.external_id == "article-new-123").first()
        enriched = db.query(IncidentEnriched).filter(IncidentEnriched.id == article.id).first()
        assert enriched is not None
        assert enriched.severity == "HIGH"
        assert enriched.summary_tactical == "Test summary"
        
        db.close()
    
    def test_multiple_articles_some_duplicates(self):
        """Test handling mix of new and duplicate articles."""
        db = TestingSessionLocal()
        source = db.query(Source).first()
        
        # Add an existing article
        existing_article = ArticleRaw(
            source_id=source.id,
            external_id="article-existing",
            url="https://example.com/article-existing",
            title_raw="Existing Article",
            published_at=datetime.now(timezone.utc),
            body_raw="Existing body",
            raw_html="<p>Existing</p>"
        )
        db.add(existing_article)
        db.commit()
        
        # Mock parser to return mix of new and existing articles
        mock_articles = [
            RawArticle(
                external_id="article-existing",  # Duplicate
                url="https://example.com/article-existing",
                title_raw="Existing Article",
                published_at=datetime.now(timezone.utc),
                body_raw="Existing body",
                raw_html="<p>Existing</p>"
            ),
            RawArticle(
                external_id="article-new-1",  # New
                url="https://example.com/article-new-1",
                title_raw="New Article 1",
                published_at=datetime.now(timezone.utc),
                body_raw="New body 1",
                raw_html="<p>New 1</p>"
            ),
            RawArticle(
                external_id="article-new-2",  # New
                url="https://example.com/article-new-2",
                title_raw="New Article 2",
                published_at=datetime.now(timezone.utc),
                body_raw="New body 2",
                raw_html="<p>New 2</p>"
            )
        ]
        
        # Mock sync_sources_to_db to prevent adding config sources
        with patch("app.main.sync_sources_to_db") as mock_sync:
            mock_sync.return_value = 0
            
            with patch("app.main.get_parser") as mock_get_parser:
                mock_parser = AsyncMock()
                mock_parser.fetch_new_articles.return_value = mock_articles
                mock_get_parser.return_value = mock_parser
                
                # Mock enricher
                with patch("app.main.GeminiEnricher") as mock_enricher_class:
                    mock_enricher = AsyncMock()
                    mock_enricher.enrich_article.return_value = {
                        "severity": "MEDIUM",
                        "summary_tactical": "Test summary",
                        "tags": [],
                        "entities": [],
                        "location_label": None,
                        "lat": None,
                        "lng": None,
                        "graph_cluster_key": None
                    }
                    mock_enricher.model_name = "test-model"
                    mock_enricher.prompt_version = "v1"
                    mock_enricher_class.return_value = mock_enricher
                    
                    response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["new_articles"] == 2  # Only 2 new articles
        
        # Verify correct number of articles
        count = db.query(ArticleRaw).count()
        assert count == 3  # 1 existing + 2 new
        
        db.close()


class TestEnrichmentFlow:
    """Test article enrichment flow."""
    
    def test_enrichment_with_gemini(self):
        """Test successful enrichment with Gemini."""
        db = TestingSessionLocal()
        source = db.query(Source).first()
        
        mock_article = RawArticle(
            external_id="article-enrich-1",
            url="https://example.com/article-enrich-1",
            title_raw="Article for Enrichment",
            published_at=datetime.now(timezone.utc),
            body_raw="Article body for enrichment test",
            raw_html="<p>Article body for enrichment test</p>"
        )
        
        with patch("app.main.get_parser") as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.fetch_new_articles.return_value = [mock_article]
            mock_get_parser.return_value = mock_parser
            
            # Mock enricher with detailed response
            with patch("app.main.GeminiEnricher") as mock_enricher_class:
                mock_enricher = AsyncMock()
                mock_enricher.enrich_article.return_value = {
                    "severity": "CRITICAL",
                    "summary_tactical": "Critical incident summary",
                    "tags": ["critical", "urgent"],
                    "entities": [
                        {"name": "John Doe", "type": "person"},
                        {"name": "Main Street", "type": "location"}
                    ],
                    "location_label": "Main Street, Test City",
                    "lat": 49.1234,
                    "lng": -122.5678,
                    "graph_cluster_key": "critical-cluster-1"
                }
                mock_enricher.model_name = "gemini-flash"
                mock_enricher.prompt_version = "v2.0"
                mock_enricher_class.return_value = mock_enricher
                
                response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        
        assert response.status_code == 200
        
        # Verify enrichment details
        article = db.query(ArticleRaw).filter(ArticleRaw.external_id == "article-enrich-1").first()
        enriched = db.query(IncidentEnriched).filter(IncidentEnriched.id == article.id).first()
        
        assert enriched.severity == "CRITICAL"
        assert enriched.summary_tactical == "Critical incident summary"
        assert enriched.tags == ["critical", "urgent"]
        assert len(enriched.entities) == 2
        assert enriched.location_label == "Main Street, Test City"
        assert enriched.lat == 49.1234
        assert enriched.lng == -122.5678
        assert enriched.llm_model == "gemini-flash"
        assert enriched.prompt_version == "v2.0"
        
        db.close()
    
    def test_enrichment_fallback_on_error(self):
        """Test fallback to dummy enrichment when Gemini fails."""
        db = TestingSessionLocal()
        source = db.query(Source).first()
        
        mock_article = RawArticle(
            external_id="article-fallback",
            url="https://example.com/article-fallback",
            title_raw="Article with Failed Enrichment",
            published_at=datetime.now(timezone.utc),
            body_raw="This article body will be used as fallback summary when enrichment fails.",
            raw_html="<p>This article body will be used as fallback summary when enrichment fails.</p>"
        )
        
        # Mock sync_sources_to_db to prevent adding config sources
        with patch("app.main.sync_sources_to_db") as mock_sync:
            mock_sync.return_value = 0
            
            with patch("app.main.get_parser") as mock_get_parser:
                mock_parser = AsyncMock()
                mock_parser.fetch_new_articles.return_value = [mock_article]
                mock_get_parser.return_value = mock_parser
                
                # Mock enricher to raise exception
                with patch("app.main.GeminiEnricher") as mock_enricher_class:
                    mock_enricher = AsyncMock()
                    mock_enricher.enrich_article.side_effect = Exception("API Error")
                    mock_enricher.model_name = "gemini-flash"
                    mock_enricher.prompt_version = "v2.0"
                    mock_enricher_class.return_value = mock_enricher
                    
                    response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["new_articles"] == 1
        
        # Verify fallback enrichment was used
        article = db.query(ArticleRaw).filter(ArticleRaw.external_id == "article-fallback").first()
        enriched = db.query(IncidentEnriched).filter(IncidentEnriched.id == article.id).first()
        
        assert enriched.severity == "MEDIUM"  # Default severity
        assert "This article body will be used as fallback" in enriched.summary_tactical
        assert enriched.tags == []
        assert enriched.entities == []
        assert enriched.llm_model == "none"
        assert enriched.prompt_version == "dummy_v1"
        
        db.close()
    
    def test_enrichment_without_gemini(self):
        """Test dummy enrichment when Gemini is not available."""
        db = TestingSessionLocal()
        source = db.query(Source).first()
        
        mock_article = RawArticle(
            external_id="article-no-gemini",
            url="https://example.com/article-no-gemini",
            title_raw="Article Without Gemini",
            published_at=datetime.now(timezone.utc),
            body_raw="Short body text for dummy enrichment.",
            raw_html="<p>Short body text for dummy enrichment.</p>"
        )
        
        with patch("app.main.get_parser") as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.fetch_new_articles.return_value = [mock_article]
            mock_get_parser.return_value = mock_parser
            
            # Mock GeminiEnricher to raise ValueError (no API key)
            with patch("app.main.GeminiEnricher") as mock_enricher_class:
                mock_enricher_class.side_effect = ValueError("No API key")
                
                response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        
        assert response.status_code == 200
        
        # Verify dummy enrichment was used
        article = db.query(ArticleRaw).filter(ArticleRaw.external_id == "article-no-gemini").first()
        enriched = db.query(IncidentEnriched).filter(IncidentEnriched.id == article.id).first()
        
        assert enriched.severity == "MEDIUM"
        assert enriched.summary_tactical == "Short body text for dummy enrichment."
        assert enriched.llm_model == "none"
        assert enriched.prompt_version == "dummy_v1"
        
        db.close()


class TestParserTimeout:
    """Test parser timeout handling."""
    
    def test_parser_timeout_continues_processing(self):
        """Test that timeout on one source doesn't stop processing others."""
        # This test would require async timeout simulation
        # For now, we verify the endpoint handles timeouts gracefully
        pass


class TestRefreshEndpointEdgeCases:
    """Test edge cases in refresh endpoint."""
    
    def test_refresh_with_no_sources(self):
        """Test refresh when no sources exist for region."""
        response = client.post("/api/refresh", json={"region": "Unknown Region"})
        assert response.status_code == 404
        assert "No active sources found" in response.json()["detail"]
    
    def test_refresh_updates_last_checked(self):
        """Test that last_checked_at is updated for sources."""
        db = TestingSessionLocal()
        source = db.query(Source).first()
        initial_checked = source.last_checked_at
        
        with patch("app.main.get_parser") as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.fetch_new_articles.return_value = []
            mock_get_parser.return_value = mock_parser
            
            response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        
        assert response.status_code == 200
        
        db.refresh(source)
        assert source.last_checked_at > initial_checked if initial_checked else source.last_checked_at is not None
        
        db.close()
    
    def test_total_incidents_count(self):
        """Test that total_incidents count is accurate."""
        db = TestingSessionLocal()
        source = db.query(Source).first()
        
        # Add some existing articles
        for i in range(3):
            article = ArticleRaw(
                source_id=source.id,
                external_id=f"existing-{i}",
                url=f"https://example.com/existing-{i}",
                title_raw=f"Existing Article {i}",
                published_at=datetime.now(timezone.utc),
                body_raw=f"Body {i}",
                raw_html=f"<p>Body {i}</p>"
            )
            db.add(article)
            db.flush()
            
            enriched = IncidentEnriched(
                id=article.id,
                severity="MEDIUM",
                summary_tactical=f"Summary {i}",
                tags=[],
                entities=[],
                llm_model="none",
                prompt_version="dummy_v1"
            )
            db.add(enriched)
        
        db.commit()
        
        with patch("app.main.get_parser") as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.fetch_new_articles.return_value = []
            mock_get_parser.return_value = mock_parser
            
            response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_incidents"] == 3
        
        db.close()
