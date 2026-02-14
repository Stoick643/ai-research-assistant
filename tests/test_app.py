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


class TestSettingsRoutes:
    """Test BYOK settings routes."""

    def test_settings_page(self, client):
        """Test settings page loads."""
        response = client.get("/settings")
        assert response.status_code == 200
        assert b"API Key Settings" in response.data
        assert b"Tavily" in response.data
        assert b"OpenAI" in response.data

    def test_save_keys(self, client):
        """Test saving API keys to session."""
        response = client.post("/settings/save",
            data={"openai_api_key": "sk-test123", "tavily_api_key": ""},
            follow_redirects=True)
        assert response.status_code == 200
        assert b"Saved keys" in response.data

    def test_save_empty_keys(self, client):
        """Test saving with no keys entered."""
        response = client.post("/settings/save",
            data={},
            follow_redirects=True)
        assert response.status_code == 200
        assert b"server defaults" in response.data

    def test_clear_keys(self, client):
        """Test clearing all keys."""
        # First save a key
        client.post("/settings/save", data={"openai_api_key": "sk-test123"})
        # Then clear
        response = client.get("/settings/clear", follow_redirects=True)
        assert response.status_code == 200
        assert b"cleared" in response.data

    def test_keys_persist_in_session(self, client):
        """Test that saved keys show up on settings page."""
        with client.session_transaction() as sess:
            sess['openai_api_key'] = 'sk-testpersist'
        response = client.get("/settings")
        assert response.status_code == 200
        assert b"Your key" in response.data

    def test_test_key_no_key(self, client):
        """Test key validation with empty key."""
        response = client.post("/api/settings/test-key",
            json={"provider": "openai", "api_key": ""},
            content_type="application/json")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is False

    def test_test_key_unknown_provider(self, client):
        """Test key validation with unknown provider."""
        response = client.post("/api/settings/test-key",
            json={"provider": "unknown", "api_key": "some-key"},
            content_type="application/json")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is False
        assert "Unknown provider" in data["message"]

    def test_home_shows_key_source(self, client):
        """Test home page shows key source labels."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Server key" in response.data or b"Your key" in response.data

    def test_user_key_overrides_server(self, client):
        """Test that user keys change what's shown on home page."""
        with client.session_transaction() as sess:
            sess['openai_api_key'] = 'sk-user-test'
        response = client.get("/")
        assert response.status_code == 200
        # Should show "Your key" for the LLM provider
        assert b"Your key" in response.data
