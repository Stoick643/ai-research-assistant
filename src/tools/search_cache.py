"""
SQLite-based search cache for avoiding duplicate Tavily API calls.
"""

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger()


class SearchCache:
    """
    SQLite-based cache for web search results.

    Provides exact-match caching keyed on query text + search parameters.
    Reduces API costs by returning cached results for repeated queries.
    """

    def __init__(
        self,
        cache_path: str = "data/cache/search_cache.db",
        ttl_hours: int = 24,
    ):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        self.logger = logger.bind(component="search_cache")

        # Stats (in-memory, reset on restart)
        self._hits = 0
        self._misses = 0

        self._init_db()

    def _init_db(self) -> None:
        """Create the cache table if it doesn't exist."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key   TEXT PRIMARY KEY,
                    query_text  TEXT NOT NULL,
                    search_depth TEXT NOT NULL,
                    max_results INTEGER NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at  REAL NOT NULL,
                    expires_at  REAL NOT NULL,
                    hit_count   INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON search_cache(expires_at)
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.cache_path))

    @staticmethod
    def _make_key(query: str, search_depth: str, max_results: int) -> str:
        """Create a deterministic cache key from search parameters."""
        raw = f"{query.strip().lower()}|{search_depth}|{max_results}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self, query: str, search_depth: str = "basic", max_results: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Look up a cached search response.

        Returns the cached Tavily response dict on hit, or None on miss.
        """
        key = self._make_key(query, search_depth, max_results)
        now = time.time()

        with self._connect() as conn:
            row = conn.execute(
                "SELECT response_json, expires_at FROM search_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()

            if row is None:
                self._misses += 1
                return None

            response_json, expires_at = row

            if now > expires_at:
                # Expired — delete and treat as miss
                conn.execute("DELETE FROM search_cache WHERE cache_key = ?", (key,))
                self._misses += 1
                self.logger.debug("Cache expired", query=query)
                return None

            # Hit — bump counter
            conn.execute(
                "UPDATE search_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (key,),
            )
            self._hits += 1
            self.logger.info("Cache hit", query=query)
            return json.loads(response_json)

    def put(
        self,
        query: str,
        search_depth: str,
        max_results: int,
        response: Dict[str, Any],
    ) -> None:
        """Store a search response in the cache."""
        key = self._make_key(query, search_depth, max_results)
        now = time.time()
        expires = now + self.ttl_hours * 3600

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO search_cache
                    (cache_key, query_text, search_depth, max_results,
                     response_json, created_at, expires_at, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (key, query.strip(), search_depth, max_results,
                 json.dumps(response), now, expires),
            )
        self.logger.debug("Cached search result", query=query)

    def clear_expired(self) -> int:
        """Delete expired entries. Returns number of rows removed."""
        now = time.time()
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM search_cache WHERE expires_at < ?", (now,)
            )
            removed = cursor.rowcount
        if removed:
            self.logger.info("Cleared expired cache entries", count=removed)
        return removed

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM search_cache"
            ).fetchone()
            entries, total_hits = row

        return {
            "entries": entries,
            "total_hits_stored": total_hits,
            "session_hits": self._hits,
            "session_misses": self._misses,
            "session_hit_rate": (
                self._hits / (self._hits + self._misses)
                if (self._hits + self._misses) > 0
                else 0.0
            ),
            "ttl_hours": self.ttl_hours,
        }
