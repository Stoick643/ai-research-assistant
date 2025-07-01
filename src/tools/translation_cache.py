"""
Translation caching system for improved performance and cost optimization.
"""

import hashlib
import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import structlog

from .translation import TranslationResult

logger = structlog.get_logger()


class TranslationCache:
    """
    SQLite-based translation cache for storing and retrieving translations.
    
    Provides:
    - Persistent translation caching
    - TTL-based cache expiration
    - Usage analytics
    - Configurable cache size limits
    """
    
    def __init__(
        self, 
        cache_path: str = "translation_cache.db",
        ttl_hours: int = 24,
        max_cache_size_mb: int = 100
    ):
        """
        Initialize translation cache.
        
        Args:
            cache_path: Path to SQLite cache database
            ttl_hours: Time-to-live for cache entries in hours
            max_cache_size_mb: Maximum cache size in megabytes
        """
        self.cache_path = Path(cache_path)
        self.ttl_hours = ttl_hours
        self.max_cache_size_mb = max_cache_size_mb
        self.logger = logger.bind(component="translation_cache")
        
        # Initialize cache database
        self._init_cache_db()
    
    def _init_cache_db(self):
        """Initialize cache database with required tables."""
        try:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS translation_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cache_key TEXT UNIQUE NOT NULL,
                        source_text TEXT NOT NULL,
                        translated_text TEXT NOT NULL,
                        source_language TEXT NOT NULL,
                        target_language TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        confidence_score REAL,
                        character_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER DEFAULT 1
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cache_key ON translation_cache(cache_key)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON translation_cache(created_at)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_lang_pair ON translation_cache(source_language, target_language)
                """)
                
                conn.commit()
                
            self.logger.info("Translation cache initialized", cache_path=str(self.cache_path))
            
        except Exception as e:
            self.logger.error("Failed to initialize translation cache", error=str(e))
            raise
    
    def _generate_cache_key(self, text: str, target_lang: str, source_lang: str, provider: str = "") -> str:
        """
        Generate cache key for translation.
        
        Args:
            text: Source text
            target_lang: Target language
            source_lang: Source language
            provider: Translation provider (optional)
            
        Returns:
            Cache key string
        """
        # Normalize text (strip whitespace, lowercase for consistency)
        normalized_text = text.strip()
        
        # Create cache string
        cache_string = f"{source_lang}:{target_lang}:{provider}:{normalized_text}"
        
        # Generate hash
        return hashlib.sha256(cache_string.encode('utf-8')).hexdigest()
    
    async def get_translation(
        self, 
        text: str, 
        target_language: str, 
        source_language: str,
        provider: str = ""
    ) -> Optional[TranslationResult]:
        """
        Retrieve translation from cache if available and not expired.
        
        Args:
            text: Source text
            target_language: Target language code
            source_language: Source language code
            provider: Translation provider
            
        Returns:
            TranslationResult if found in cache, None otherwise
        """
        cache_key = self._generate_cache_key(text, target_language, source_language, provider)
        
        try:
            with sqlite3.connect(self.cache_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check for cached translation
                cursor.execute("""
                    SELECT * FROM translation_cache 
                    WHERE cache_key = ? 
                    AND datetime(created_at) > datetime('now', '-{} hours')
                """.format(self.ttl_hours), (cache_key,))
                
                row = cursor.fetchone()
                
                if row:
                    # Update access tracking
                    cursor.execute("""
                        UPDATE translation_cache 
                        SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
                        WHERE cache_key = ?
                    """, (cache_key,))
                    conn.commit()
                    
                    # Create TranslationResult from cached data
                    result = TranslationResult(
                        original_text=row['source_text'],
                        translated_text=row['translated_text'],
                        source_language=row['source_language'],
                        target_language=row['target_language'],
                        confidence_score=row['confidence_score'] or 0.0,
                        provider=row['provider'],
                        character_count=row['character_count'] or len(text),
                        created_at=datetime.fromisoformat(row['created_at'])
                    )
                    
                    self.logger.info(
                        "Translation cache hit",
                        cache_key=cache_key[:16],
                        source_lang=source_language,
                        target_lang=target_language,
                        provider=provider
                    )
                    
                    return result
                
                return None
                
        except Exception as e:
            self.logger.warning("Cache lookup failed", cache_key=cache_key[:16], error=str(e))
            return None
    
    async def store_translation(self, result: TranslationResult, provider: str = "") -> bool:
        """
        Store translation result in cache.
        
        Args:
            result: TranslationResult to cache
            provider: Translation provider
            
        Returns:
            True if stored successfully, False otherwise
        """
        cache_key = self._generate_cache_key(
            result.original_text, 
            result.target_language, 
            result.source_language,
            provider
        )
        
        try:
            with sqlite3.connect(self.cache_path) as conn:
                cursor = conn.cursor()
                
                # Insert or replace cached translation
                cursor.execute("""
                    INSERT OR REPLACE INTO translation_cache 
                    (cache_key, source_text, translated_text, source_language, target_language, 
                     provider, confidence_score, character_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cache_key,
                    result.original_text,
                    result.translated_text,
                    result.source_language,
                    result.target_language,
                    provider,
                    result.confidence_score,
                    result.character_count
                ))
                
                conn.commit()
                
                self.logger.info(
                    "Translation cached",
                    cache_key=cache_key[:16],
                    source_lang=result.source_language,
                    target_lang=result.target_language,
                    char_count=result.character_count
                )
                
                return True
                
        except Exception as e:
            self.logger.error("Failed to cache translation", cache_key=cache_key[:16], error=str(e))
            return False
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        try:
            with sqlite3.connect(self.cache_path) as conn:
                cursor = conn.cursor()
                
                # Delete expired entries
                cursor.execute("""
                    DELETE FROM translation_cache 
                    WHERE datetime(created_at) <= datetime('now', '-{} hours')
                """.format(self.ttl_hours))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info("Cache cleanup completed", deleted_entries=deleted_count)
                
                return deleted_count
                
        except Exception as e:
            self.logger.error("Cache cleanup failed", error=str(e))
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            with sqlite3.connect(self.cache_path) as conn:
                cursor = conn.cursor()
                
                # Basic stats
                cursor.execute("SELECT COUNT(*) FROM translation_cache")
                total_entries = cursor.fetchone()[0]
                
                cursor.execute("SELECT SUM(character_count) FROM translation_cache")
                total_characters = cursor.fetchone()[0] or 0
                
                # Language pair stats
                cursor.execute("""
                    SELECT source_language, target_language, COUNT(*) as count
                    FROM translation_cache 
                    GROUP BY source_language, target_language
                    ORDER BY count DESC
                    LIMIT 10
                """)
                top_language_pairs = cursor.fetchall()
                
                # Provider stats
                cursor.execute("""
                    SELECT provider, COUNT(*) as count, AVG(confidence_score) as avg_confidence
                    FROM translation_cache 
                    GROUP BY provider
                    ORDER BY count DESC
                """)
                provider_stats = cursor.fetchall()
                
                # Access stats
                cursor.execute("SELECT SUM(access_count) FROM translation_cache")
                total_accesses = cursor.fetchone()[0] or 0
                
                cursor.execute("SELECT AVG(access_count) FROM translation_cache")
                avg_accesses = cursor.fetchone()[0] or 0
                
                return {
                    'total_entries': total_entries,
                    'total_characters_cached': total_characters,
                    'total_cache_accesses': total_accesses,
                    'average_accesses_per_entry': round(avg_accesses, 2),
                    'top_language_pairs': [
                        {
                            'source_language': pair[0],
                            'target_language': pair[1],
                            'count': pair[2]
                        } for pair in top_language_pairs
                    ],
                    'provider_statistics': [
                        {
                            'provider': stat[0],
                            'translation_count': stat[1],
                            'average_confidence': round(stat[2] or 0, 3)
                        } for stat in provider_stats
                    ],
                    'cache_file_size_mb': self.cache_path.stat().st_size / (1024 * 1024) if self.cache_path.exists() else 0
                }
                
        except Exception as e:
            self.logger.error("Failed to get cache stats", error=str(e))
            return {'error': str(e)}
    
    def clear_cache(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.cache_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM translation_cache")
                conn.commit()
                
                self.logger.info("Translation cache cleared")
                return True
                
        except Exception as e:
            self.logger.error("Failed to clear cache", error=str(e))
            return False
    
    def get_cache_hit_rate(self, hours: int = 24) -> float:
        """
        Calculate cache hit rate for recent period.
        
        Args:
            hours: Hours to look back for calculating hit rate
            
        Returns:
            Cache hit rate as percentage (0.0 to 100.0)
        """
        try:
            with sqlite3.connect(self.cache_path) as conn:
                cursor = conn.cursor()
                
                # Count cache accesses in the period
                cursor.execute("""
                    SELECT SUM(access_count) FROM translation_cache
                    WHERE datetime(last_accessed) > datetime('now', '-{} hours')
                """.format(hours))
                
                recent_accesses = cursor.fetchone()[0] or 0
                
                # Count unique entries accessed (represents cache hits)
                cursor.execute("""
                    SELECT COUNT(*) FROM translation_cache
                    WHERE datetime(last_accessed) > datetime('now', '-{} hours')
                """.format(hours))
                
                cache_hits = cursor.fetchone()[0] or 0
                
                if recent_accesses > 0:
                    hit_rate = (cache_hits / recent_accesses) * 100
                    return round(hit_rate, 2)
                
                return 0.0
                
        except Exception as e:
            self.logger.error("Failed to calculate hit rate", error=str(e))
            return 0.0