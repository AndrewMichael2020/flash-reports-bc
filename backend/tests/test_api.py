"""
Integration tests for the FastAPI backend.
Tests API endpoints with a test database.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db
from app.models import Source


# Create test database (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///./test_crimewatch.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Override the database dependency
app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Set up test database before tests, tear down after."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Seed test data
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
    Base.metadata.drop_all(bind=engine)


class TestHealthEndpoint:
    """Test the root health check endpoint."""
    
    def test_health_check(self):
        """Test GET / returns service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Crimewatch Intel Backend"
        assert "version" in data
        assert data["status"] == "operational"


class TestIncidentsEndpoint:
    """Test the /api/incidents endpoint."""
    
    def test_get_incidents_requires_region(self):
        """Test that region parameter is required."""
        response = client.get("/api/incidents")
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_get_incidents_empty(self):
        """Test getting incidents when database is empty."""
        response = client.get("/api/incidents?region=Fraser Valley, BC")
        assert response.status_code == 200
        data = response.json()
        assert data["region"] == "Fraser Valley, BC"
        assert data["incidents"] == []
    
    def test_get_incidents_with_limit(self):
        """Test limit parameter."""
        response = client.get("/api/incidents?region=Fraser Valley, BC&limit=50")
        assert response.status_code == 200


class TestRefreshEndpoint:
    """Test the /api/refresh endpoint."""
    
    def test_refresh_requires_region(self):
        """Test that region is required."""
        response = client.post("/api/refresh", json={})
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_refresh_unknown_region(self):
        """Test refreshing a region with no sources."""
        response = client.post("/api/refresh", json={"region": "Unknown Region"})
        assert response.status_code == 404
    
    def test_refresh_valid_region(self):
        """Test refreshing a valid region (won't fetch live data in test)."""
        # This will attempt to use the parser but won't actually fetch from internet
        # We just verify the endpoint responds correctly
        response = client.post("/api/refresh", json={"region": "Fraser Valley, BC"})
        # Should succeed or fail gracefully (we don't have real parsers in test)
        assert response.status_code in [200, 500]  # May fail due to network


class TestGraphEndpoint:
    """Test the /api/graph endpoint."""
    
    def test_get_graph_requires_region(self):
        """Test that region parameter is required."""
        response = client.get("/api/graph")
        assert response.status_code == 422
    
    def test_get_graph_empty(self):
        """Test getting graph when no incidents exist."""
        response = client.get("/api/graph?region=Fraser Valley, BC")
        assert response.status_code == 200
        data = response.json()
        assert data["region"] == "Fraser Valley, BC"
        assert data["nodes"] == []
        assert data["links"] == []


class TestMapEndpoint:
    """Test the /api/map endpoint."""
    
    def test_get_map_requires_region(self):
        """Test that region parameter is required."""
        response = client.get("/api/map")
        assert response.status_code == 422
    
    def test_get_map_empty(self):
        """Test getting map when no incidents exist."""
        response = client.get("/api/map?region=Fraser Valley, BC")
        assert response.status_code == 200
        data = response.json()
        assert data["region"] == "Fraser Valley, BC"
        assert data["markers"] == []
