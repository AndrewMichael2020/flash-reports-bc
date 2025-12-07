"""
Tests for CORS configuration.
Verify that CORS headers are properly set for preflight and actual requests.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestCORS:
    """Test CORS headers for various origins."""
    
    def test_preflight_localhost(self):
        """Test OPTIONS preflight for localhost origin."""
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = client.options("/api/refresh", headers=headers)
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "access-control-allow-methods" in response.headers
        assert "POST" in response.headers["access-control-allow-methods"]
    
    def test_preflight_github_codespaces(self):
        """Test OPTIONS preflight for GitHub Codespaces origin."""
        origin = "https://verbose-train-75g546r7qp9fwpxp-3000.app.github.dev"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = client.options("/api/refresh", headers=headers)
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        # Should match the origin via regex
        assert response.headers["access-control-allow-origin"] == origin
        assert "access-control-allow-methods" in response.headers
        assert "POST" in response.headers["access-control-allow-methods"]
    
    def test_actual_post_with_cors(self):
        """Test actual POST request with CORS headers."""
        origin = "https://verbose-train-75g546r7qp9fwpxp-3000.app.github.dev"
        headers = {
            "Origin": origin,
            "Content-Type": "application/json",
        }
        # This will fail because region doesn't exist, but should have CORS headers
        response = client.post(
            "/api/refresh",
            json={"region": "Test Region"},
            headers=headers
        )
        # Should have CORS header regardless of success/failure
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == origin
    
    def test_get_with_cors(self):
        """Test GET request with CORS headers."""
        origin = "http://localhost:5173"
        headers = {"Origin": origin}
        response = client.get("/api/incidents?region=Test", headers=headers)
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == origin
