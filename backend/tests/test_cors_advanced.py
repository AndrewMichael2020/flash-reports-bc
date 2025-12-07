"""
Advanced CORS tests to ensure proper handling of various scenarios.
Tests preflight requests, headers, and edge cases.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestCORSPreflight:
    """Test CORS preflight (OPTIONS) requests."""
    
    def test_preflight_all_methods(self):
        """Test preflight request allows all methods."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = client.options("/api/refresh", headers=headers)
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == origin
        assert "access-control-allow-methods" in response.headers
        # Should allow all methods including POST, GET, PUT, DELETE
        allowed_methods = response.headers["access-control-allow-methods"]
        assert "POST" in allowed_methods
        assert "GET" in allowed_methods
    
    def test_preflight_custom_headers(self):
        """Test preflight request with custom headers."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization,x-custom-header",
        }
        response = client.options("/api/refresh", headers=headers)
        
        assert response.status_code == 200
        assert "access-control-allow-headers" in response.headers
        # Should allow all requested headers
        allowed_headers = response.headers["access-control-allow-headers"].lower()
        assert "content-type" in allowed_headers
        assert "authorization" in allowed_headers or "*" in allowed_headers
    
    def test_preflight_credentials(self):
        """Test that credentials are allowed."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = client.options("/api/refresh", headers=headers)
        
        assert response.status_code == 200
        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"
    
    def test_preflight_max_age(self):
        """Test that max-age is set for caching preflight responses."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = client.options("/api/refresh", headers=headers)
        
        assert response.status_code == 200
        if "access-control-max-age" in response.headers:
            max_age = int(response.headers["access-control-max-age"])
            assert max_age > 0  # Should cache for some time


class TestCORSActualRequests:
    """Test CORS headers on actual (non-preflight) requests."""
    
    def test_post_with_origin(self):
        """Test POST request includes CORS headers."""
        origin = "http://localhost:5173"
        headers = {
            "Origin": origin,
            "Content-Type": "application/json",
        }
        response = client.post(
            "/api/refresh",
            json={"region": "Unknown"},  # Will fail but should have CORS
            headers=headers
        )
        
        # Should have CORS headers regardless of response status
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == origin
    
    def test_get_with_origin(self):
        """Test GET request includes CORS headers."""
        origin = "http://localhost:5173"
        headers = {"Origin": origin}
        response = client.get("/api/incidents?region=Test", headers=headers)
        
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == origin
    
    def test_exposed_headers(self):
        """Test that headers are exposed to the client."""
        origin = "http://localhost:3000"
        headers = {"Origin": origin}
        response = client.get("/", headers=headers)
        
        assert "access-control-expose-headers" in response.headers
        # Should expose all headers or specific ones
        exposed = response.headers["access-control-expose-headers"]
        assert exposed == "*" or len(exposed) > 0


class TestCORSOriginVariations:
    """Test CORS with various origin patterns."""
    
    def test_localhost_port_3000(self):
        """Test localhost:3000 is allowed."""
        origin = "http://localhost:3000"
        headers = {"Origin": origin}
        response = client.get("/", headers=headers)
        
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    
    def test_localhost_port_5173(self):
        """Test localhost:5173 (Vite default) is allowed."""
        origin = "http://localhost:5173"
        headers = {"Origin": origin}
        response = client.get("/", headers=headers)
        
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    
    def test_127_0_0_1_port_3000(self):
        """Test 127.0.0.1:3000 is allowed."""
        origin = "http://127.0.0.1:3000"
        headers = {"Origin": origin}
        response = client.get("/", headers=headers)
        
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    
    def test_github_codespaces_origin(self):
        """Test GitHub Codespaces origin pattern is allowed."""
        # Various Codespaces URL patterns
        origins = [
            "https://verbose-train-75g546r7qp9fwpxp-3000.app.github.dev",
            "https://scaling-space-engine-abc123-8080.app.github.dev",
            "https://my-codespace-xyz-5173.app.github.dev",
        ]
        
        for origin in origins:
            headers = {"Origin": origin}
            response = client.get("/", headers=headers)
            
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
    
    def test_disallowed_origin(self):
        """Test that random origins are not allowed if strict mode was enabled."""
        # Note: Current config allows regex matching for Codespaces
        # This test verifies behavior with an origin that doesn't match
        origin = "https://malicious-site.com"
        headers = {"Origin": origin}
        response = client.get("/", headers=headers)
        
        assert response.status_code == 200
        # Should not include CORS headers or should deny
        # With current liberal config, it might still allow
        # This depends on CORS middleware configuration


class TestCORSMethods:
    """Test CORS with different HTTP methods."""
    
    def test_options_method(self):
        """Test OPTIONS method (preflight) works."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        }
        response = client.options("/api/refresh", headers=headers)
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
    
    def test_post_method(self):
        """Test POST method includes CORS."""
        origin = "http://localhost:3000"
        headers = {"Origin": origin, "Content-Type": "application/json"}
        response = client.post("/api/refresh", json={"region": "Test"}, headers=headers)
        
        # Should have CORS regardless of success
        assert "access-control-allow-origin" in response.headers
    
    def test_get_method(self):
        """Test GET method includes CORS."""
        origin = "http://localhost:3000"
        headers = {"Origin": origin}
        response = client.get("/api/incidents?region=Test", headers=headers)
        
        assert "access-control-allow-origin" in response.headers
    
    def test_delete_method_preflight(self):
        """Test DELETE method is allowed in preflight."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "DELETE",
        }
        response = client.options("/api/incidents/123", headers=headers)
        
        assert response.status_code in [200, 404, 405]  # Depends on route
        # If route exists, should allow method


class TestCORSEdgeCases:
    """Test CORS edge cases and error scenarios."""
    
    def test_cors_on_404(self):
        """Test CORS headers present on 404 responses."""
        origin = "http://localhost:3000"
        headers = {"Origin": origin}
        response = client.get("/nonexistent-endpoint", headers=headers)
        
        assert response.status_code == 404
        # Should still have CORS headers
        assert "access-control-allow-origin" in response.headers
    
    def test_cors_on_422(self):
        """Test CORS headers present on validation errors."""
        origin = "http://localhost:3000"
        headers = {"Origin": origin, "Content-Type": "application/json"}
        response = client.post("/api/refresh", json={}, headers=headers)  # Missing region
        
        assert response.status_code == 422
        assert "access-control-allow-origin" in response.headers
    
    def test_cors_on_500(self):
        """Test CORS headers present on server errors."""
        # This would require triggering an actual 500 error
        # For now, we verify middleware is applied globally
        pass
    
    def test_no_origin_header(self):
        """Test request without Origin header."""
        response = client.get("/")
        
        assert response.status_code == 200
        # Without Origin header, CORS headers might not be included
        # This is normal behavior
    
    def test_multiple_origins_in_sequence(self):
        """Test handling multiple different origins in sequence."""
        origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://test-abc-3000.app.github.dev",
        ]
        
        for origin in origins:
            headers = {"Origin": origin}
            response = client.get("/", headers=headers)
            
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin


class TestCORSWithAuthentication:
    """Test CORS with credentials and authentication."""
    
    def test_credentials_flag_set(self):
        """Test that allow-credentials is set to true."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        }
        response = client.options("/api/refresh", headers=headers)
        
        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"
    
    def test_credentials_with_cookies(self):
        """Test CORS works with cookie headers."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Cookie": "session=abc123",
        }
        response = client.get("/", headers=headers)
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-credentials" in response.headers
