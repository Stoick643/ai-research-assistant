"""
Tests for the SearchCache module.
"""

import pytest
import tempfile
import os
import time

from src.tools.search_cache import SearchCache


class TestSearchCache:
    """Test suite for SearchCache."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        c = SearchCache(cache_path=path, ttl_hours=1)
        yield c
        try:
            os.unlink(path)
        except OSError:
            pass

    def test_put_and_get(self, cache):
        """Test basic cache store and retrieve."""
        response = {"results": [{"title": "Test", "url": "http://example.com"}]}
        cache.put("quantum computing", "basic", 5, response)

        result = cache.get("quantum computing", "basic", 5)
        assert result is not None
        assert result["results"][0]["title"] == "Test"

    def test_cache_miss(self, cache):
        """Test cache miss returns None."""
        result = cache.get("nonexistent query", "basic", 5)
        assert result is None

    def test_case_insensitive(self, cache):
        """Test that queries are case-insensitive."""
        response = {"results": []}
        cache.put("Quantum Computing", "basic", 5, response)

        result = cache.get("quantum computing", "basic", 5)
        assert result is not None

    def test_different_params_different_keys(self, cache):
        """Test that different search params produce different cache keys."""
        response_basic = {"results": [{"depth": "basic"}]}
        response_advanced = {"results": [{"depth": "advanced"}]}

        cache.put("test query", "basic", 5, response_basic)
        cache.put("test query", "advanced", 5, response_advanced)

        basic = cache.get("test query", "basic", 5)
        advanced = cache.get("test query", "advanced", 5)

        assert basic["results"][0]["depth"] == "basic"
        assert advanced["results"][0]["depth"] == "advanced"

    def test_expiration(self, cache):
        """Test that expired entries are not returned."""
        # Create cache with very short TTL
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        short_cache = SearchCache(cache_path=path, ttl_hours=0)  # 0 hours = instant expiry

        response = {"results": []}
        short_cache.put("test", "basic", 5, response)
        time.sleep(0.1)

        result = short_cache.get("test", "basic", 5)
        assert result is None

        try:
            os.unlink(path)
        except OSError:
            pass

    def test_hit_count(self, cache):
        """Test that hit count is incremented."""
        response = {"results": []}
        cache.put("test", "basic", 5, response)

        cache.get("test", "basic", 5)
        cache.get("test", "basic", 5)
        cache.get("test", "basic", 5)

        stats = cache.get_stats()
        assert stats["session_hits"] == 3
        assert stats["session_misses"] == 0

    def test_stats(self, cache):
        """Test cache statistics."""
        response = {"results": []}
        cache.put("query1", "basic", 5, response)
        cache.put("query2", "basic", 5, response)

        cache.get("query1", "basic", 5)  # hit
        cache.get("query3", "basic", 5)  # miss

        stats = cache.get_stats()
        assert stats["entries"] == 2
        assert stats["session_hits"] == 1
        assert stats["session_misses"] == 1
        assert stats["session_hit_rate"] == 0.5

    def test_clear_expired(self, cache):
        """Test clearing expired entries."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        short_cache = SearchCache(cache_path=path, ttl_hours=0)

        short_cache.put("old", "basic", 5, {"results": []})
        time.sleep(0.1)

        removed = short_cache.clear_expired()
        assert removed == 1

        stats = short_cache.get_stats()
        assert stats["entries"] == 0

        try:
            os.unlink(path)
        except OSError:
            pass

    def test_overwrite_existing(self, cache):
        """Test that putting same key overwrites."""
        cache.put("test", "basic", 5, {"version": 1})
        cache.put("test", "basic", 5, {"version": 2})

        result = cache.get("test", "basic", 5)
        assert result["version"] == 2

        stats = cache.get_stats()
        assert stats["entries"] == 1
