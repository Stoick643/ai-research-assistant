"""
Embedding providers for semantic search cache.

Supports:
- HashEmbedding: zero-dependency hash-based vectorizer (default)
- OpenAIEmbedding: high-quality embeddings via OpenAI API (optional)
"""

import hashlib
import math
import struct
from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np
import structlog

logger = structlog.get_logger()

# Embedding dimensions
HASH_DIMENSIONS = 256
OPENAI_DIMENSIONS = 1536  # text-embedding-3-small


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""
    
    @property
    @abstractmethod
    def dimensions(self) -> int:
        pass
    
    @property
    def recommended_threshold(self) -> float:
        """Recommended similarity threshold for this provider."""
        return 0.85
    
    @abstractmethod
    def embed(self, text: str) -> bytes:
        """Return embedding as packed float bytes for sqlite-vec."""
        pass
    
    def embed_float(self, text: str) -> List[float]:
        """Return embedding as list of floats."""
        raw = self.embed(text)
        n = self.dimensions
        return list(struct.unpack(f'{n}f', raw))


class HashEmbedding(EmbeddingProvider):
    """
    Hash-based embedding using the hashing trick.
    
    Zero external dependencies. Works well for short text (search queries).
    Generates a fixed-size vector by hashing words and n-grams into positions.
    """
    
    def __init__(self, dimensions: int = HASH_DIMENSIONS):
        self._dimensions = dimensions
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    @property
    def recommended_threshold(self) -> float:
        # Hash embeddings produce lower absolute cosine values than neural models
        return 0.20
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize into words, bigrams, and trigrams."""
        # Lowercase, strip punctuation, split
        cleaned = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in text.lower())
        words = cleaned.split()
        
        tokens = list(words)  # unigrams
        
        # Bigrams
        for i in range(len(words) - 1):
            tokens.append(f"{words[i]}_{words[i+1]}")
        
        # Trigrams
        for i in range(len(words) - 2):
            tokens.append(f"{words[i]}_{words[i+1]}_{words[i+2]}")
        
        return tokens
    
    def embed(self, text: str) -> bytes:
        """Generate hash-based embedding."""
        vec = np.zeros(self._dimensions, dtype=np.float32)
        tokens = self._tokenize(text)
        
        if not tokens:
            return vec.tobytes()
        
        for token in tokens:
            # Hash to get position and sign
            h = hashlib.md5(token.encode()).hexdigest()
            pos = int(h[:8], 16) % self._dimensions
            sign = 1.0 if int(h[8:16], 16) % 2 == 0 else -1.0
            vec[pos] += sign
        
        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        
        return vec.tobytes()


class OpenAIEmbedding(EmbeddingProvider):
    """
    OpenAI text-embedding-3-small provider.
    
    High quality embeddings, costs ~$0.00002/1K tokens.
    Requires OpenAI API key.
    """
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        import openai
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self._dimensions = OPENAI_DIMENSIONS
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    def embed(self, text: str) -> bytes:
        """Generate embedding via OpenAI API."""
        response = self.client.embeddings.create(
            model=self.model,
            input=text.strip()
        )
        vec = np.array(response.data[0].embedding, dtype=np.float32)
        return vec.tobytes()


def create_embedding_provider(
    openai_api_key: Optional[str] = None,
    provider: str = "auto"
) -> EmbeddingProvider:
    """
    Create the best available embedding provider.
    
    Args:
        openai_api_key: OpenAI API key (enables high-quality embeddings)
        provider: "auto", "hash", or "openai"
    
    Returns:
        EmbeddingProvider instance
    """
    if provider == "openai" and openai_api_key:
        logger.info("Using OpenAI embeddings", model="text-embedding-3-small")
        return OpenAIEmbedding(api_key=openai_api_key)
    
    if provider == "auto" and openai_api_key:
        try:
            ep = OpenAIEmbedding(api_key=openai_api_key)
            # Quick validation
            ep.embed("test")
            logger.info("Using OpenAI embeddings (auto-detected)")
            return ep
        except Exception as e:
            logger.warning("OpenAI embeddings unavailable, falling back to hash", error=str(e))
    
    logger.info("Using hash-based embeddings", dimensions=HASH_DIMENSIONS)
    return HashEmbedding()
