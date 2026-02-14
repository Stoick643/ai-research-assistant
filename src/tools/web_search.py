"""
Web search tool using Tavily API for AI-optimized search results.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os
from tavily import TavilyClient
import structlog

logger = structlog.get_logger()


@dataclass
class SearchResult:
    """Structured search result from Tavily API."""
    title: str
    url: str
    content: str
    score: float
    published_date: Optional[str] = None


@dataclass
class SearchResponse:
    """Complete search response with metadata."""
    query: str
    results: List[SearchResult]
    answer: Optional[str] = None
    follow_up_questions: List[str] = None
    search_context: Optional[str] = None
    images: List[Dict[str, str]] = None
    cache_hit: bool = False


class WebSearchTool:
    """Tavily-powered web search tool optimized for AI agents."""
    
    def __init__(self, api_key: Optional[str] = None, search_cache=None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("Tavily API key not found. Set TAVILY_API_KEY environment variable")
        
        self.client = TavilyClient(api_key=self.api_key)
        self.search_cache = search_cache
        self.logger = logger.bind(tool="web_search")
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text to handle Unicode encoding issues."""
        if not text:
            return ""
        
        try:
            # Handle case where text might have encoding issues
            if isinstance(text, str):
                # Try to encode and decode to clean up any encoding issues
                normalized = text.encode('utf-8', errors='replace').decode('utf-8')
                return normalized
            return str(text)
        except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
            # If all else fails, replace problematic characters
            return str(text).encode('ascii', errors='replace').decode('ascii')

    async def search(
        self, 
        query: str, 
        max_results: int = 5, 
        search_depth: str = "basic", 
        include_answer: bool = True, 
        include_images: bool = False, 
        include_raw_content: bool = False, 
        days: Optional[int] = None
    ) -> SearchResponse:
        """
        Perform web search using Tavily API.
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            search_depth: "basic" or "advanced" search depth
            include_answer: Whether to include AI-generated answer
            include_images: Whether to include image results
            include_raw_content: Whether to include raw HTML content
            days: Limit results to past N days
            
        Returns:
            SearchResponse with results and metadata
        """
        # Normalize query to handle Unicode issues
        normalized_query = self._normalize_text(query)
        self.logger.info("Performing web search", query=normalized_query, max_results=max_results)
        
        # Check cache first
        if self.search_cache:
            cached = self.search_cache.get(normalized_query, search_depth, max_results)
            if cached is not None:
                return self._parse_response(normalized_query, cached, include_answer, include_images, cache_hit=True)
        
        try:
            # Run Tavily search in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.search(
                    query=normalized_query,
                    search_depth=search_depth,
                    max_results=max_results,
                    include_answer=include_answer,
                    include_images=include_images,
                    include_raw_content=include_raw_content,
                    days=days
                )
            )
            
            # Store in cache before parsing
            if self.search_cache and isinstance(response, dict):
                self.search_cache.put(normalized_query, search_depth, max_results, response)

            return self._parse_response(normalized_query, response, include_answer, include_images)
            
        except Exception as e:
            self.logger.error("Web search failed", query=query, error=str(e))
            raise RuntimeError(f"Web search failed: {str(e)}") from e

    def _parse_response(
        self,
        query: str,
        response: Dict[str, Any],
        include_answer: bool = True,
        include_images: bool = False,
        cache_hit: bool = False,
    ) -> SearchResponse:
        """Parse a raw Tavily response dict into a SearchResponse."""
        results = []

        raw_results = response.get("results") if isinstance(response, dict) else None

        if raw_results is None:
            self.logger.warning("Tavily returned None for results", query=query)
            raw_results = []
        elif not isinstance(raw_results, list):
            self.logger.warning("Tavily returned non-list results", type=type(raw_results), query=query)
            raw_results = []

        for result in raw_results:
            search_result = SearchResult(
                title=self._normalize_text(result.get("title", "")),
                url=result.get("url", ""),
                content=self._normalize_text(result.get("content", "")),
                score=float(result.get("score", 0.0)),
                published_date=result.get("published_date"),
            )
            results.append(search_result)

        search_response = SearchResponse(
            query=query,
            results=results,
            answer=self._normalize_text(response.get("answer", "")) if include_answer and response.get("answer") else None,
            follow_up_questions=[self._normalize_text(q) for q in (response.get("follow_up_questions") or [])],
            search_context=self._normalize_text(response.get("search_context", "")),
            images=response.get("images", []) if include_images else None,
            cache_hit=cache_hit,
        )

        self.logger.info(
            "Web search completed",
            query=query,
            results_count=len(results),
            has_answer=bool(search_response.answer),
            cache_hit=cache_hit,
        )

        return search_response
    
    async def get_search_context(
        self, 
        query: str, 
        max_results: int = 5, 
        search_depth: str = "basic"
    ) -> str:
        """
        Get search context optimized for RAG applications.
        
        Args:
            query: The search query
            max_results: Maximum number of results
            search_depth: Search depth level
            
        Returns:
            Concatenated search context suitable for RAG
        """
        self.logger.info("Getting search context", query=query)
        
        try:
            loop = asyncio.get_event_loop()
            context = await loop.run_in_executor(
                None,
                lambda: self.client.get_search_context(
                    query=query,
                    search_depth=search_depth,
                    max_results=max_results
                )
            )
            
            self.logger.info("Search context retrieved", query=query, context_length=len(context))
            return context
            
        except Exception as e:
            self.logger.error("Failed to get search context", query=query, error=str(e))
            raise RuntimeError(f"Failed to get search context: {str(e)}") from e
    
    async def qna_search(self, query: str) -> str:
        """
        Get a direct answer to a question using Tavily's QnA feature.
        
        Args:
            query: The question to answer
            
        Returns:
            Direct answer string
        """
        self.logger.info("Performing QnA search", query=query)
        
        try:
            loop = asyncio.get_event_loop()
            answer = await loop.run_in_executor(
                None,
                lambda: self.client.qna_search(query=query)
            )
            
            self.logger.info("QnA search completed", query=query, answer_length=len(answer))
            return answer
            
        except Exception as e:
            self.logger.error("QnA search failed", query=query, error=str(e))
            raise RuntimeError(f"QnA search failed: {str(e)}") from e
    
    async def extract_url_content(self, url: str) -> str:
        """
        Extract content from a specific URL using Tavily.
        
        Args:
            url: The URL to extract content from
            
        Returns:
            Extracted content as string
        """
        self.logger.info("Extracting URL content", url=url)
        
        try:
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                lambda: self.client.extract(url=url)
            )
            
            self.logger.info("URL content extracted", url=url, content_length=len(content))
            return content
            
        except Exception as e:
            self.logger.error("URL content extraction failed", url=url, error=str(e))
            raise RuntimeError(f"URL content extraction failed: {str(e)}") from e