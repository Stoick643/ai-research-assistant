"""
Tests for the WebSearchTool module.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from src.tools.web_search import WebSearchTool, SearchResult, SearchResponse


class TestWebSearchTool:
    """Test suite for WebSearchTool."""
    
    def test_init_with_api_key(self):
        """Test initialization with provided API key."""
        tool = WebSearchTool(api_key="test-key")
        assert tool.api_key == "test-key"
    
    def test_init_without_api_key_with_env(self):
        """Test initialization without API key but with environment variable."""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "env-key"}):
            tool = WebSearchTool()
            assert tool.api_key == "env-key"
    
    def test_init_without_api_key_no_env(self):
        """Test initialization fails without API key or environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Tavily API key not found"):
                WebSearchTool()
    
    @pytest.fixture
    def mock_tavily_response(self):
        """Load mock Tavily API response from fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "mock_tavily_response.json"
        with open(fixture_path, 'r') as f:
            return json.load(f)
    
    @pytest.fixture
    def web_search_tool(self):
        """Create WebSearchTool instance for testing."""
        return WebSearchTool(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_search_success(self, web_search_tool, mock_tavily_response):
        """Test successful web search."""
        with patch.object(web_search_tool.client, 'search', return_value=mock_tavily_response):
            result = await web_search_tool.search("AI trends 2025")
            
            assert isinstance(result, SearchResponse)
            assert result.query == "AI trends 2025"
            assert len(result.results) == 5
            assert result.answer is not None
            assert len(result.follow_up_questions) > 0
            
            # Test first search result
            first_result = result.results[0]
            assert isinstance(first_result, SearchResult)
            assert first_result.title == "Top AI Trends Shaping 2025: Generative AI and Beyond"
            assert first_result.score == 0.95
            assert first_result.url == "https://example.com/ai-trends-2025"
    
    @pytest.mark.asyncio
    async def test_search_with_parameters(self, web_search_tool, mock_tavily_response):
        """Test search with various parameters."""
        with patch.object(web_search_tool.client, 'search', return_value=mock_tavily_response) as mock_search:
            await web_search_tool.search(
                query="test query",
                max_results=10,
                search_depth="advanced",
                include_answer=False,
                include_images=True,
                days=7
            )
            
            mock_search.assert_called_once_with(
                query="test query",
                search_depth="advanced",
                max_results=10,
                include_answer=False,
                include_images=True,
                include_raw_content=False,
                days=7
            )
    
    @pytest.mark.asyncio
    async def test_search_api_error(self, web_search_tool):
        """Test search with API error."""
        with patch.object(web_search_tool.client, 'search', side_effect=Exception("API Error")):
            with pytest.raises(RuntimeError, match="Web search failed: API Error"):
                await web_search_tool.search("test query")
    
    @pytest.mark.asyncio
    async def test_get_search_context_success(self, web_search_tool):
        """Test successful search context retrieval."""
        mock_context = "This is search context for the query."
        
        with patch.object(web_search_tool.client, 'get_search_context', return_value=mock_context):
            result = await web_search_tool.get_search_context("test query")
            
            assert result == mock_context
    
    @pytest.mark.asyncio
    async def test_get_search_context_error(self, web_search_tool):
        """Test search context with API error."""
        with patch.object(web_search_tool.client, 'get_search_context', side_effect=Exception("Context Error")):
            with pytest.raises(RuntimeError, match="Failed to get search context: Context Error"):
                await web_search_tool.get_search_context("test query")
    
    @pytest.mark.asyncio
    async def test_qna_search_success(self, web_search_tool):
        """Test successful QnA search."""
        mock_answer = "This is the answer to the question."
        
        with patch.object(web_search_tool.client, 'qna_search', return_value=mock_answer):
            result = await web_search_tool.qna_search("What is AI?")
            
            assert result == mock_answer
    
    @pytest.mark.asyncio
    async def test_qna_search_error(self, web_search_tool):
        """Test QnA search with API error."""
        with patch.object(web_search_tool.client, 'qna_search', side_effect=Exception("QnA Error")):
            with pytest.raises(RuntimeError, match="QnA search failed: QnA Error"):
                await web_search_tool.qna_search("test question")
    
    @pytest.mark.asyncio
    async def test_extract_url_content_success(self, web_search_tool):
        """Test successful URL content extraction."""
        mock_content = "This is the extracted content from the URL."
        
        with patch.object(web_search_tool.client, 'extract', return_value=mock_content):
            result = await web_search_tool.extract_url_content("https://example.com")
            
            assert result == mock_content
    
    @pytest.mark.asyncio
    async def test_extract_url_content_error(self, web_search_tool):
        """Test URL content extraction with error."""
        with patch.object(web_search_tool.client, 'extract', side_effect=Exception("Extract Error")):
            with pytest.raises(RuntimeError, match="URL content extraction failed: Extract Error"):
                await web_search_tool.extract_url_content("https://example.com")


class TestSearchResult:
    """Test suite for SearchResult dataclass."""
    
    def test_search_result_creation(self):
        """Test SearchResult creation."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            content="Test content",
            score=0.95,
            published_date="2024-01-01"
        )
        
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.content == "Test content"
        assert result.score == 0.95
        assert result.published_date == "2024-01-01"
    
    def test_search_result_optional_date(self):
        """Test SearchResult with optional published_date."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            content="Test content",
            score=0.8
        )
        
        assert result.published_date is None


class TestSearchResponse:
    """Test suite for SearchResponse dataclass."""
    
    def test_search_response_creation(self):
        """Test SearchResponse creation."""
        results = [
            SearchResult("Title 1", "https://example1.com", "Content 1", 0.9),
            SearchResult("Title 2", "https://example2.com", "Content 2", 0.8)
        ]
        
        response = SearchResponse(
            query="test query",
            results=results,
            answer="Test answer",
            follow_up_questions=["Question 1", "Question 2"],
            search_context="Test context",
            images=[{"url": "https://example.com/image.jpg"}]
        )
        
        assert response.query == "test query"
        assert len(response.results) == 2
        assert response.answer == "Test answer"
        assert len(response.follow_up_questions) == 2
        assert response.search_context == "Test context"
        assert len(response.images) == 1
    
    def test_search_response_minimal(self):
        """Test SearchResponse with minimal data."""
        response = SearchResponse(
            query="test query",
            results=[]
        )
        
        assert response.query == "test query"
        assert response.results == []
        assert response.answer is None
        assert response.follow_up_questions is None
        assert response.search_context is None
        assert response.images is None