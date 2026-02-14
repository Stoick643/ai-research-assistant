"""
Smoke tests for the Flask application.
"""

import pytest
import os
from unittest.mock import patch


@pytest.fixture
def client():
    """Create Flask test client with mocked API keys."""
    env = {
        "OPENAI_API_KEY": "test-key",
        "TAVILY_API_KEY": "test-tavily-key",
    }
    with patch.dict(os.environ, env):
        from app import create_production_app
        app = create_production_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client


class TestAppRoutes:
    """Test that all routes respond."""

    def test_home(self, client):
        """Test home page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"AI Research Assistant" in response.data
        assert b"Start AI Research" in response.data

    def test_history(self, client):
        """Test history page loads."""
        response = client.get("/history")
        assert response.status_code == 200
        assert b"Research History" in response.data

    def test_health(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"

    def test_research_not_found(self, client):
        """Test viewing non-existent research redirects."""
        response = client.get("/research/99999", follow_redirects=True)
        assert response.status_code == 200
        # Should redirect to home with flash message

    def test_download_not_found(self, client):
        """Test downloading non-existent research redirects."""
        response = client.get("/research/99999/download", follow_redirects=True)
        assert response.status_code == 200

    def test_submit_research_too_short(self, client):
        """Test that short topics are rejected."""
        response = client.post("/submit_research",
            data={"topic": "short", "language": "en", "depth": "basic"},
            follow_redirects=True)
        assert response.status_code == 200
        assert b"at least 10 characters" in response.data

    def test_api_status_not_found(self, client):
        """Test API status for non-existent research."""
        response = client.get("/api/research/99999/status")
        assert response.status_code == 404

    def test_404_handler(self, client):
        """Test 404 error handler."""
        response = client.get("/nonexistent-page")
        assert response.status_code == 404
