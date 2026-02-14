"""
Tests for semantic search cache with sqlite-vec.
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.tools.search_cache import SearchCache
from src.tools.embeddings import HashEmbedding, EmbeddingProvider


@pytest.fixture
def embedding_provider():
    """Create hash embedding provider for tests."""
    return HashEmbedding(dimensions=256)


@pytest.fixture
def cache(tmp_path, embedding_provider):
    """Create search cache with semantic search enabled (uses provider's recommended threshold)."""
    return SearchCache(
        cache_path=str(tmp_path / "test_cache.db"),
        ttl_hours=24,
        embedding_provider=embedding_provider,
    )


@pytest.fixture
def cache_no_vec(tmp_path):
    """Create search cache without semantic search."""
    return SearchCache(
        cache_path=str(tmp_path / "test_cache_novec.db"),
        ttl_hours=24,
        embedding_provider=None,
    )


class TestHashEmbedding:
    """Tests for hash-based embedding provider."""

    def test_dimensions(self, embedding_provider):
        assert embedding_provider.dimensions == 256

    def test_embed_returns_bytes(self, embedding_provider):
        result = embedding_provider.embed("test query")
        assert isinstance(result, bytes)
        assert len(result) == 256 * 4  # 256 floats * 4 bytes each

    def test_embed_deterministic(self, embedding_provider):
        """Same input produces same embedding."""
        a = embedding_provider.embed("quantum computing basics")
        b = embedding_provider.embed("quantum computing basics")
        assert a == b

    def test_embed_different_for_different_text(self, embedding_provider):
        """Different inputs produce different embeddings."""
        a = embedding_provider.embed("quantum computing")
        b = embedding_provider.embed("cooking recipes")
        assert a != b

    def test_similar_text_closer_distance(self, embedding_provider):
        """Similar queries should have smaller distance than dissimilar ones."""
        import numpy as np
        
        base = np.frombuffer(embedding_provider.embed("quantum computing basics"), dtype=np.float32)
        similar = np.frombuffer(embedding_provider.embed("introduction to quantum computing"), dtype=np.float32)
        different = np.frombuffer(embedding_provider.embed("best chocolate cake recipe"), dtype=np.float32)
        
        dist_similar = np.linalg.norm(base - similar)
        dist_different = np.linalg.norm(base - different)
        
        assert dist_similar < dist_different

    def test_embed_empty_string(self, embedding_provider):
        """Empty string should return zero vector."""
        result = embedding_provider.embed("")
        assert isinstance(result, bytes)
        assert len(result) == 256 * 4

    def test_embed_float_returns_list(self, embedding_provider):
        """embed_float should return list of floats."""
        result = embedding_provider.embed_float("test")
        assert isinstance(result, list)
        assert len(result) == 256
        assert all(isinstance(x, float) for x in result)


class TestSearchCacheExactMatch:
    """Tests for exact-match caching (should still work as before)."""

    def test_put_and_get(self, cache):
        response = {"results": [{"title": "Test"}], "answer": "Test answer"}
        cache.put("quantum computing", "basic", 5, response)
        result = cache.get("quantum computing", "basic", 5)
        assert result == response

    def test_cache_miss(self, cache):
        result = cache.get("nonexistent query", "basic", 5)
        assert result is None

    def test_case_insensitive(self, cache):
        response = {"results": [{"title": "Test"}]}
        cache.put("Quantum Computing", "basic", 5, response)
        result = cache.get("quantum computing", "basic", 5)
        assert result == response

    def test_different_params_different_keys(self, cache):
        response1 = {"results": [{"title": "Basic"}]}
        response2 = {"results": [{"title": "Advanced"}]}
        cache.put("query", "basic", 5, response1)
        cache.put("query", "advanced", 5, response2)
        
        assert cache.get("query", "basic", 5) == response1
        assert cache.get("query", "advanced", 5) == response2

    def test_expiration(self, cache):
        response = {"results": []}
        cache.put("query", "basic", 5, response)
        
        # Manually expire
        import sqlite3
        with sqlite3.connect(str(cache.cache_path)) as conn:
            conn.execute("UPDATE search_cache SET expires_at = ?", (time.time() - 1,))
        
        result = cache.get("query", "basic", 5)
        assert result is None


class TestSearchCacheSemantic:
    """Tests for semantic vector search."""

    def test_semantic_hit_similar_query(self, cache):
        """Similar queries should return cached result."""
        response = {"results": [{"title": "Quantum"}], "answer": "Quantum info"}
        cache.put("quantum computing basics for beginners", "basic", 5, response)
        
        # Different wording, same meaning
        result = cache.get("introduction to quantum computing fundamentals", "basic", 5)
        
        if cache._vec_available:
            # If sqlite-vec loaded, should find semantic match
            assert result is not None
            assert result == response
        else:
            # Without sqlite-vec, only exact match works
            assert result is None

    def test_semantic_miss_very_different_query(self, cache):
        """Very different queries should NOT match."""
        response = {"results": [{"title": "Quantum"}]}
        cache.put("quantum computing research papers", "basic", 5, response)
        
        result = cache.get("best chocolate cake recipe", "basic", 5)
        assert result is None

    def test_semantic_respects_search_depth(self, cache):
        """Semantic match should still require same search_depth."""
        response = {"results": [{"title": "Test"}]}
        cache.put("quantum computing basics", "basic", 5, response)
        
        # Same query but different depth — should NOT match
        result = cache.get("quantum computing basics", "advanced", 5)
        assert result is None

    def test_stats_include_semantic(self, cache):
        """Stats should include semantic hit count."""
        stats = cache.get_stats()
        assert "session_semantic_hits" in stats
        assert "semantic_enabled" in stats

    def test_semantic_disabled_without_provider(self, cache_no_vec):
        """Cache without embedding provider should work (exact-match only)."""
        response = {"results": [{"title": "Test"}]}
        cache_no_vec.put("test query", "basic", 5, response)
        
        # Exact match works
        result = cache_no_vec.get("test query", "basic", 5)
        assert result == response
        
        # No semantic match
        stats = cache_no_vec.get_stats()
        assert stats["semantic_enabled"] is False

    def test_clear_expired_cleans_vectors(self, cache):
        """Clearing expired entries should also clean vector table."""
        import sqlite3
        
        response = {"results": []}
        cache.put("expired query", "basic", 5, response)
        
        # Manually expire
        with sqlite3.connect(str(cache.cache_path)) as conn:
            conn.execute("UPDATE search_cache SET expires_at = ?", (time.time() - 1,))
            if cache._vec_available:
                conn.execute("UPDATE search_vec_meta SET expires_at = ?", (time.time() - 1,))
        
        removed = cache.clear_expired()
        assert removed == 1


class TestSearchCacheBackwardCompat:
    """Ensure backward compatibility with existing code."""

    def test_works_without_embedding_provider(self, tmp_path):
        """Cache should work exactly as before without embedding provider."""
        cache = SearchCache(
            cache_path=str(tmp_path / "compat.db"),
            embedding_provider=None,
        )
        
        response = {"results": [{"title": "Test"}]}
        cache.put("test", "basic", 5, response)
        assert cache.get("test", "basic", 5) == response
        assert cache.get("other", "basic", 5) is None

    def test_hit_count(self, tmp_path):
        """Hit count should still increment."""
        cache = SearchCache(cache_path=str(tmp_path / "hits.db"), embedding_provider=None)
        
        response = {"results": []}
        cache.put("query", "basic", 5, response)
        cache.get("query", "basic", 5)
        cache.get("query", "basic", 5)
        
        stats = cache.get_stats()
        assert stats["total_hits_stored"] == 2
