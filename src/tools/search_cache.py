"""
SQLite-based search cache with exact-match and semantic vector search.

Uses sqlite-vec for semantic similarity matching on cache miss.
Falls back to exact-match only if sqlite-vec is unavailable.
"""

import hashlib
import json
import sqlite3
import struct
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import structlog

logger = structlog.get_logger()


def _load_vec(conn: sqlite3.Connection) -> bool:
    """Try to load sqlite-vec extension. Returns True on success."""
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        return True
    except (ImportError, Exception) as e:
        logger.debug("sqlite-vec not available", error=str(e))
        return False


class SearchCache:
    """
    SQLite-based cache for web search results.

    Provides:
    - Exact-match caching keyed on query text + search parameters
    - Semantic vector search for similar queries (via sqlite-vec)
    - Automatic fallback to exact-match if sqlite-vec unavailable
    """

    def __init__(
        self,
        cache_path: str = "data/cache/search_cache.db",
        ttl_hours: int = 24,
        similarity_threshold: float = None,
        embedding_provider=None,
    ):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        self.embedding_provider = embedding_provider
        # Use provider's recommended threshold unless explicitly set
        if similarity_threshold is None and embedding_provider:
            self.similarity_threshold = embedding_provider.recommended_threshold
        else:
            self.similarity_threshold = similarity_threshold if similarity_threshold is not None else 0.85
        self.logger = logger.bind(component="search_cache")

        # Stats (in-memory, reset on restart)
        self._hits = 0
        self._misses = 0
        self._semantic_hits = 0

        # Check if sqlite-vec is available
        self._vec_available = False
        self._init_db()

    def _init_db(self) -> None:
        """Create cache tables (exact + vector)."""
        with self._connect() as conn:
            # Exact-match table (unchanged from Phase 1)
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
            
            # Try to set up vector table
            if _load_vec(conn) and self.embedding_provider:
                try:
                    dims = self.embedding_provider.dimensions
                    conn.execute(f"""
                        CREATE VIRTUAL TABLE IF NOT EXISTS search_vec
                        USING vec0(embedding float[{dims}])
                    """)
                    # Metadata table linking vec rowid to cache_key
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS search_vec_meta (
                            rowid       INTEGER PRIMARY KEY,
                            cache_key   TEXT NOT NULL,
                            query_text  TEXT NOT NULL,
                            search_depth TEXT NOT NULL,
                            max_results INTEGER NOT NULL,
                            created_at  REAL NOT NULL,
                            expires_at  REAL NOT NULL,
                            FOREIGN KEY (cache_key) REFERENCES search_cache(cache_key)
                        )
                    """)
                    self._vec_available = True
                    self.logger.info("Semantic search cache enabled",
                                   dimensions=dims,
                                   threshold=self.similarity_threshold)
                except Exception as e:
                    self.logger.warning("Failed to create vector table", error=str(e))
                    self._vec_available = False
            else:
                self.logger.info("Semantic search cache disabled (no embedding provider or sqlite-vec)")

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

        1. Try exact match first
        2. On miss, try semantic vector search (if available)
        3. Return None if no match found
        """
        # Phase 1: Exact match
        result = self._get_exact(query, search_depth, max_results)
        if result is not None:
            self._hits += 1
            return result
        
        # Phase 2: Semantic match
        if self._vec_available and self.embedding_provider:
            result = self._get_semantic(query, search_depth, max_results)
            if result is not None:
                self._semantic_hits += 1
                return result
        
        self._misses += 1
        return None

    def _get_exact(
        self, query: str, search_depth: str, max_results: int
    ) -> Optional[Dict[str, Any]]:
        """Exact-match cache lookup."""
        key = self._make_key(query, search_depth, max_results)
        now = time.time()

        with self._connect() as conn:
            row = conn.execute(
                "SELECT response_json, expires_at FROM search_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()

            if row is None:
                return None

            response_json, expires_at = row

            if now > expires_at:
                conn.execute("DELETE FROM search_cache WHERE cache_key = ?", (key,))
                self.logger.debug("Cache expired", query=query)
                return None

            conn.execute(
                "UPDATE search_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (key,),
            )
            self.logger.info("Cache hit (exact)", query=query)
            return json.loads(response_json)

    def _get_semantic(
        self, query: str, search_depth: str, max_results: int
    ) -> Optional[Dict[str, Any]]:
        """Semantic vector similarity search."""
        now = time.time()
        
        try:
            query_embedding = self.embedding_provider.embed(query)
        except Exception as e:
            self.logger.warning("Failed to generate query embedding", error=str(e))
            return None

        with self._connect() as conn:
            if not _load_vec(conn):
                return None
            
            try:
                # Find nearest vector within threshold
                # sqlite-vec returns L2 distance; convert threshold to max distance
                # For normalized vectors: L2_distance = sqrt(2 * (1 - cosine_similarity))
                max_distance = (2.0 * (1.0 - self.similarity_threshold)) ** 0.5
                
                rows = conn.execute("""
                    SELECT v.rowid, v.distance, m.cache_key, m.query_text, m.expires_at
                    FROM search_vec v
                    JOIN search_vec_meta m ON v.rowid = m.rowid
                    WHERE v.embedding MATCH ?
                      AND k = 3
                    ORDER BY v.distance
                """, (query_embedding,)).fetchall()
                
                for rowid, distance, cache_key, cached_query, expires_at in rows:
                    # Skip expired
                    if now > expires_at:
                        continue
                    
                    # Skip if too far
                    if distance > max_distance:
                        continue
                    
                    # Check that search params match (depth + max_results)
                    cached_row = conn.execute(
                        "SELECT response_json, search_depth, max_results FROM search_cache WHERE cache_key = ?",
                        (cache_key,),
                    ).fetchone()
                    
                    if cached_row is None:
                        continue
                    
                    response_json, cached_depth, cached_max = cached_row
                    
                    # Depth and max_results must match
                    if cached_depth != search_depth or cached_max != max_results:
                        continue
                    
                    # Semantic hit!
                    cosine_sim = 1.0 - (distance ** 2) / 2.0
                    conn.execute(
                        "UPDATE search_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                        (cache_key,),
                    )
                    self.logger.info("Cache hit (semantic)",
                                   query=query,
                                   matched_query=cached_query,
                                   similarity=round(cosine_sim, 3),
                                   distance=round(distance, 4))
                    return json.loads(response_json)
                
            except Exception as e:
                self.logger.warning("Semantic search failed", error=str(e))
        
        return None

    def put(
        self,
        query: str,
        search_depth: str,
        max_results: int,
        response: Dict[str, Any],
    ) -> None:
        """Store a search response in the cache (exact + vector)."""
        key = self._make_key(query, search_depth, max_results)
        now = time.time()
        expires = now + self.ttl_hours * 3600

        with self._connect() as conn:
            # Store in exact-match table
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
            
            # Store vector embedding if available
            if self._vec_available and self.embedding_provider:
                try:
                    if not _load_vec(conn):
                        return
                    
                    embedding = self.embedding_provider.embed(query)
                    
                    # Insert into vector table (auto-assigns rowid)
                    conn.execute(
                        "INSERT INTO search_vec(embedding) VALUES (?)",
                        (embedding,),
                    )
                    rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    
                    # Store metadata linking rowid to cache_key
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO search_vec_meta
                            (rowid, cache_key, query_text, search_depth, max_results, created_at, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (rowid, key, query.strip(), search_depth, max_results, now, expires),
                    )
                    self.logger.debug("Stored vector embedding", query=query)
                except Exception as e:
                    self.logger.warning("Failed to store vector embedding", error=str(e))
        
        self.logger.debug("Cached search result", query=query)

    def clear_expired(self) -> int:
        """Delete expired entries from both exact and vector tables."""
        now = time.time()
        with self._connect() as conn:
            # Get expired cache keys before deleting
            expired_keys = [row[0] for row in conn.execute(
                "SELECT cache_key FROM search_cache WHERE expires_at < ?", (now,)
            ).fetchall()]
            
            # Delete from exact table
            cursor = conn.execute(
                "DELETE FROM search_cache WHERE expires_at < ?", (now,)
            )
            removed = cursor.rowcount
            
            # Delete from vector tables if available
            if self._vec_available and expired_keys:
                try:
                    if _load_vec(conn):
                        for key in expired_keys:
                            row = conn.execute(
                                "SELECT rowid FROM search_vec_meta WHERE cache_key = ?", (key,)
                            ).fetchone()
                            if row:
                                conn.execute("DELETE FROM search_vec WHERE rowid = ?", (row[0],))
                                conn.execute("DELETE FROM search_vec_meta WHERE rowid = ?", (row[0],))
                except Exception as e:
                    self.logger.warning("Failed to clean vector cache", error=str(e))
        
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

        total_lookups = self._hits + self._semantic_hits + self._misses
        return {
            "entries": entries,
            "total_hits_stored": total_hits,
            "session_hits": self._hits,
            "session_semantic_hits": self._semantic_hits,
            "session_misses": self._misses,
            "session_hit_rate": (
                (self._hits + self._semantic_hits) / total_lookups
                if total_lookups > 0
                else 0.0
            ),
            "ttl_hours": self.ttl_hours,
            "semantic_enabled": self._vec_available,
            "similarity_threshold": self.similarity_threshold,
        }
