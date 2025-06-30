"""
Tests for the ResearchAgent module.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from src.agents.research_agent import ResearchAgent
from src.tools.web_search import WebSearchTool, SearchResponse, SearchResult
from src.tools.report_writer import MarkdownWriter
from src.utils.llm import LLMClient


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""
    
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
    
    async def generate(self, system_prompt, user_message, **kwargs):
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
        else:
            response = f"Mock response for: {user_message[:50]}..."
        
        self.call_count += 1
        return response


class TestResearchAgent:
    """Test suite for ResearchAgent."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        return MockLLMClient([
            "1. AI trends 2025 overview\n2. Generative AI applications\n3. AI safety developments",
            "AI is experiencing rapid growth in 2025 with significant advances in generative AI.",
            "Key findings:\n1. Generative AI mainstream adoption\n2. AI safety focus\n3. Edge AI growth",
            "AI is transforming industries with generative AI becoming mainstream in business applications.",
            "Summary of AI trends"
        ])
    
    @pytest.fixture
    def mock_web_search_tool(self):
        """Create mock web search tool."""
        tool = Mock(spec=WebSearchTool)
        
        # Mock search results
        search_results = [
            SearchResult(
                title="AI Trends 2025",
                url="https://example.com/ai-trends",
                content="AI is advancing rapidly in 2025...",
                score=0.95
            ),
            SearchResult(
                title="Generative AI Report",
                url="https://example.com/gen-ai",
                content="Generative AI is becoming mainstream...",
                score=0.90
            )
        ]
        
        search_response = SearchResponse(
            query="AI trends 2025",
            results=search_results,
            answer="AI is experiencing significant growth in 2025",
            follow_up_questions=["What about AI safety?", "How is edge AI developing?"]
        )
        
        tool.search = AsyncMock(return_value=search_response)
        return tool
    
    @pytest.fixture
    def mock_report_writer(self):
        """Create mock report writer."""
        writer = Mock(spec=MarkdownWriter)
        writer.save_report = AsyncMock(return_value="/tmp/test_report.md")
        return writer
    
    @pytest.fixture
    def research_agent(self, mock_llm_client, mock_web_search_tool, mock_report_writer):
        """Create ResearchAgent instance for testing."""
        return ResearchAgent(
            name="TestResearchAgent",
            llm_client=mock_llm_client,
            web_search_tool=mock_web_search_tool,
            report_writer=mock_report_writer,
            max_search_queries=3
        )
    
    def test_init(self, mock_llm_client):
        """Test ResearchAgent initialization."""
        agent = ResearchAgent(
            name="TestAgent",
            llm_client=mock_llm_client,
            max_search_queries=5
        )
        
        assert agent.name == "TestAgent"
        assert agent.max_search_queries == 5
        assert agent.research_queries == []
        assert agent.all_search_results == []
        assert agent.research_start_time is None
    
    @pytest.mark.asyncio
    async def test_generate_search_queries(self, research_agent, mock_llm_client):
        """Test search query generation."""
        mock_llm_client.responses = [
            "AI trends 2025 overview\nGenerative AI applications\nAI safety and governance"
        ]
        mock_llm_client.call_count = 0
        
        queries = await research_agent._generate_search_queries("AI trends 2025")
        
        assert len(queries) <= research_agent.max_search_queries
        assert len(queries) == 3
        assert "AI trends 2025 overview" in queries
        assert "Generative AI applications" in queries
        assert "AI safety and governance" in queries
    
    @pytest.mark.asyncio
    async def test_generate_search_queries_with_focus(self, research_agent, mock_llm_client):
        """Test search query generation with focus areas."""
        mock_llm_client.responses = [
            "Generative AI business applications\nAI safety in healthcare\nEdge AI development"
        ]
        mock_llm_client.call_count = 0
        
        queries = await research_agent._generate_search_queries(
            "AI trends 2025", 
            focus_areas=["healthcare", "business"]
        )
        
        assert len(queries) <= research_agent.max_search_queries
        assert len(queries) == 3
    
    @pytest.mark.asyncio
    async def test_execute_searches(self, research_agent, mock_web_search_tool):
        """Test search execution."""
        queries = ["AI trends 2025", "Generative AI", "AI safety"]
        
        responses = await research_agent._execute_searches(queries)
        
        assert len(responses) == 3
        assert len(research_agent.research_queries) == 3
        assert len(research_agent.all_search_results) == 6  # 2 results per search * 3 searches
        
        # Verify search calls
        assert mock_web_search_tool.search.call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_searches_with_failures(self, research_agent, mock_web_search_tool):
        """Test search execution with some failures."""
        # Mock one failure
        mock_web_search_tool.search.side_effect = [
            SearchResponse("query1", [SearchResult("Title1", "url1", "content1", 0.9)]),
            Exception("Search failed"),
            SearchResponse("query3", [SearchResult("Title3", "url3", "content3", 0.8)])
        ]
        
        queries = ["query1", "query2", "query3"]
        responses = await research_agent._execute_searches(queries)
        
        assert len(responses) == 2  # Only successful searches
        assert len(research_agent.research_queries) == 2
    
    @pytest.mark.asyncio
    async def test_analyze_sources(self, research_agent, mock_llm_client):
        """Test source analysis."""
        search_responses = [
            SearchResponse(
                "AI trends",
                [SearchResult("Title1", "url1", "Content1", 0.9)],
                answer="AI is growing"
            )
        ]
        
        mock_llm_client.responses = ["Comprehensive analysis of AI trends..."]
        mock_llm_client.call_count = 0
        
        analysis = await research_agent._analyze_sources("AI trends 2025", search_responses)
        
        assert analysis == "Comprehensive analysis of AI trends..."
        assert mock_llm_client.call_count == 1
    
    @pytest.mark.asyncio
    async def test_extract_key_findings(self, research_agent, mock_llm_client):
        """Test key findings extraction."""
        analysis = "AI is growing rapidly with several key developments..."
        
        mock_llm_client.responses = [
            "Generative AI is mainstream\nAI safety is a priority\nEdge AI is emerging"
        ]
        mock_llm_client.call_count = 0
        
        findings = await research_agent._extract_key_findings(analysis)
        
        assert len(findings) <= 5
        assert "Generative AI is mainstream" in findings
        assert "AI safety is a priority" in findings
        assert "Edge AI is emerging" in findings
    
    @pytest.mark.asyncio
    async def test_extract_executive_summary(self, research_agent, mock_llm_client):
        """Test executive summary extraction."""
        analysis = "Detailed analysis of AI trends..."
        
        mock_llm_client.responses = ["AI is experiencing unprecedented growth in 2025..."]
        mock_llm_client.call_count = 0
        
        summary = await research_agent._extract_executive_summary(analysis)
        
        assert summary == "AI is experiencing unprecedented growth in 2025..."
        assert mock_llm_client.call_count == 1
    
    @pytest.mark.asyncio
    async def test_generate_report(self, research_agent, mock_llm_client):
        """Test report generation."""
        analysis = "Comprehensive analysis of AI trends..."
        search_responses = [
            SearchResponse(
                "AI trends",
                [SearchResult("AI Report", "https://example.com", "Content", 0.95)],
                answer="AI answer"
            )
        ]
        
        mock_llm_client.responses = [
            "Finding 1\nFinding 2\nFinding 3",  # Key findings
            "Executive summary of AI trends"      # Executive summary
        ]
        mock_llm_client.call_count = 0
        research_agent.research_start_time = 1000.0
        research_agent.research_queries = ["query1", "query2"]
        
        with patch('time.time', return_value=1045.0):  # 45 seconds later
            report = await research_agent._generate_report("AI Trends 2025", analysis, search_responses)
        
        assert "# Research Report: AI Trends 2025" in report
        assert "## Executive Summary" in report
        assert "## Key Findings" in report
        assert "## Detailed Analysis" in report
        assert "## Sources" in report
        assert "## Metadata" in report
        assert "45.0 seconds" in report
    
    @pytest.mark.asyncio
    async def test_save_research_report(self, research_agent, mock_report_writer):
        """Test research report saving."""
        research_agent.research_queries = ["query1", "query2"]
        research_agent.all_search_results = [
            SearchResult("Title1", "url1", "content1", 0.9),
            SearchResult("Title2", "url2", "content2", 0.8)
        ]
        
        report_content = "# Research Report\n\nContent here..."
        processing_time = 30.5
        
        result_path = await research_agent._save_research_report(
            "AI Trends 2025", 
            report_content, 
            processing_time
        )
        
        assert result_path == "/tmp/test_report.md"
        mock_report_writer.save_report.assert_called_once()
        
        # Check call arguments
        call_args = mock_report_writer.save_report.call_args
        assert call_args[1]['content'] == report_content
        assert "ai_trends_2025" in call_args[1]['filename']
        assert call_args[1]['metadata']['query_count'] == 2
        assert call_args[1]['metadata']['source_count'] == 2
        assert call_args[1]['metadata']['processing_time'] == 30.5
    
    @pytest.mark.asyncio
    async def test_conduct_research_full_workflow(self, research_agent, mock_llm_client, mock_web_search_tool, mock_report_writer):
        """Test full research workflow."""
        # Setup mock responses
        mock_llm_client.responses = [
            "AI trends overview\nGenerative AI\nAI safety",  # Search queries
            "Comprehensive analysis of AI trends...",         # Source analysis
            "Finding 1\nFinding 2\nFinding 3",              # Key findings
            "Executive summary of the research"              # Executive summary
        ]
        mock_llm_client.call_count = 0
        
        topic = "AI Trends 2025"
        focus_areas = ["business", "technology"]
        
        result = await research_agent.conduct_research(topic, focus_areas)
        
        # Verify result structure
        assert result['topic'] == topic
        assert result['report_path'] == "/tmp/test_report.md"
        assert 'report_content' in result
        assert 'total_queries' in result
        assert 'total_sources' in result
        assert 'processing_time' in result
        assert 'analysis' in result
        assert 'search_queries' in result
        
        # Verify calls were made
        assert mock_web_search_tool.search.call_count >= 1
        mock_report_writer.save_report.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_plan_research_goal(self, research_agent):
        """Test planning for research goals."""
        tasks = await research_agent.plan("research AI trends 2025")
        
        expected_tasks = [
            "Generate targeted search queries",
            "Execute web searches", 
            "Analyze and synthesize sources",
            "Generate structured report",
            "Save research report"
        ]
        
        assert tasks == expected_tasks
    
    @pytest.mark.asyncio
    async def test_plan_non_research_goal(self, research_agent):
        """Test planning for non-research goals falls back to parent."""
        # This should fall back to parent's plan method
        with patch.object(research_agent.__class__.__bases__[0], 'plan') as mock_parent_plan:
            mock_parent_plan.return_value = ["Task 1", "Task 2"]
            
            tasks = await research_agent.plan("solve math problem")
            
            mock_parent_plan.assert_called_once_with("solve math problem")
            assert tasks == ["Task 1", "Task 2"]
    
    @pytest.mark.asyncio
    async def test_execute_task_research(self, research_agent):
        """Test executing research tasks."""
        # Mock the conduct_research method
        mock_result = {
            'report_path': '/tmp/test.md',
            'total_queries': 3,
            'total_sources': 10,
            'processing_time': 45.0
        }
        
        with patch.object(research_agent, 'conduct_research', return_value=mock_result):
            result = await research_agent.execute_task("research AI trends")
            
            assert result['task'] == "research AI trends"
            assert result['status'] == "completed"
            assert "Research completed" in result['result']
            assert result['metadata']['report_path'] == '/tmp/test.md'
    
    @pytest.mark.asyncio
    async def test_execute_task_non_research(self, research_agent):
        """Test executing non-research tasks falls back to parent."""
        with patch.object(research_agent.__class__.__bases__[0], 'execute_task') as mock_parent_execute:
            mock_parent_execute.return_value = {"task": "math", "status": "completed"}
            
            result = await research_agent.execute_task("solve equation")
            
            mock_parent_execute.assert_called_once_with("solve equation")
            assert result == {"task": "math", "status": "completed"}