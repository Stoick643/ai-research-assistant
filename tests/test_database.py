"""
Tests for database functionality including models, SQLiteWriter, and analytics.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch
from pathlib import Path

from src.database.models import Research, Query, Source, Base, create_database_engine, create_tables
from src.database.database import DatabaseManager
from src.database.sqlite_writer import SQLiteWriter
from src.database.analytics import ResearchAnalytics


class TestDatabaseModels:
    """Test database models and relationships."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def db_manager(self, temp_db_path):
        """Create database manager with temporary database."""
        manager = DatabaseManager(database_path=temp_db_path)
        manager.initialize()
        return manager
    
    def test_research_model_creation(self, db_manager):
        """Test creating Research model instances."""
        with db_manager.get_session() as session:
            research = Research(
                topic="Test AI Research",
                agent_name="TestAgent",
                focus_areas=["machine learning", "neural networks"],
                processing_time=45.5,
                status="completed",
                executive_summary="Test summary",
                key_findings=["Finding 1", "Finding 2"],
                detailed_analysis="Detailed test analysis",
                total_queries=3,
                total_sources=15
            )
            
            session.add(research)
            session.commit()
            
            # Verify record was created
            saved_research = session.query(Research).filter(Research.topic == "Test AI Research").first()
            assert saved_research is not None
            assert saved_research.agent_name == "TestAgent"
            assert saved_research.focus_areas == ["machine learning", "neural networks"]
            assert saved_research.processing_time == 45.5
            assert saved_research.key_findings == ["Finding 1", "Finding 2"]
    
    def test_query_model_relationships(self, db_manager):
        """Test Query model and relationships."""
        with db_manager.get_session() as session:
            # Create research
            research = Research(topic="Test Research", agent_name="TestAgent")
            session.add(research)
            session.flush()
            
            # Create query
            query = Query(
                research_id=research.id,
                query_text="AI trends 2024",
                query_order=1,
                max_results=5,
                search_depth="basic",
                results_count=3,
                ai_answer="AI is advancing rapidly",
                follow_up_questions=["What about safety?", "How about ethics?"],
                execution_time=2.5,
                success=True
            )
            session.add(query)
            session.commit()
            
            # Verify relationships
            saved_research = session.query(Research).filter(Research.id == research.id).first()
            assert len(saved_research.queries) == 1
            assert saved_research.queries[0].query_text == "AI trends 2024"
            assert saved_research.queries[0].follow_up_questions == ["What about safety?", "How about ethics?"]
    
    def test_source_model_domain_extraction(self, db_manager):
        """Test Source model and domain extraction."""
        with db_manager.get_session() as session:
            # Create research and query
            research = Research(topic="Test Research", agent_name="TestAgent")
            session.add(research)
            session.flush()
            
            query = Query(research_id=research.id, query_text="test", query_order=1)
            session.add(query)
            session.flush()
            
            # Create source
            source = Source(
                research_id=research.id,
                query_id=query.id,
                title="Test Article",
                url="https://example.com/article",
                content="Test content about AI",
                relevance_score=0.95,
                published_date="2024-01-15",
                content_length=100,
                used_in_analysis=True
            )
            source.extract_domain()  # Test domain extraction
            session.add(source)
            session.commit()
            
            # Verify source and domain extraction
            saved_source = session.query(Source).filter(Source.title == "Test Article").first()
            assert saved_source.domain == "example.com"
            assert saved_source.relevance_score == 0.95
            assert saved_source.used_in_analysis is True
    
    def test_research_to_dict(self, db_manager):
        """Test Research model to_dict method."""
        with db_manager.get_session() as session:
            research = Research(
                topic="Test Research",
                agent_name="TestAgent",
                focus_areas=["AI", "ML"],
                processing_time=30.0,
                status="completed",
                metadata={"test": "value"}
            )
            session.add(research)
            session.commit()
            
            research_dict = research.to_dict()
            assert research_dict["topic"] == "Test Research"
            assert research_dict["agent_name"] == "TestAgent"
            assert research_dict["focus_areas"] == ["AI", "ML"]
            assert research_dict["processing_time"] == 30.0
            assert research_dict["status"] == "completed"
            assert research_dict["metadata"] == {"test": "value"}


class TestDatabaseManager:
    """Test DatabaseManager functionality."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    def test_database_manager_initialization(self, temp_db_path):
        """Test database manager initialization."""
        manager = DatabaseManager(database_path=temp_db_path)
        manager.initialize()
        
        # Verify database file was created
        assert os.path.exists(temp_db_path)
        
        # Test database URL construction
        expected_url = f"sqlite:///{temp_db_path}"
        assert manager.database_url == expected_url
    
    def test_database_stats(self, temp_db_path):
        """Test database statistics functionality."""
        manager = DatabaseManager(database_path=temp_db_path)
        manager.initialize()
        
        # Add test data
        with manager.get_session() as session:
            research = Research(
                topic="Test Research",
                agent_name="TestAgent",
                processing_time=25.5,
                status="completed"
            )
            session.add(research)
            session.flush()
            
            query = Query(research_id=research.id, query_text="test", query_order=1)
            session.add(query)
            session.flush()
            
            source = Source(
                research_id=research.id,
                query_id=query.id,
                title="Test Source",
                url="https://example.com",
                content="Test content",
                relevance_score=0.8
            )
            session.add(source)
        
        # Get stats
        stats = manager.get_database_stats()
        assert stats["total_research_sessions"] == 1
        assert stats["completed_sessions"] == 1
        assert stats["total_queries"] == 1
        assert stats["total_sources"] == 1
        assert stats["average_processing_time"] == 25.5
    
    def test_cleanup_old_data(self, temp_db_path):
        """Test cleanup of old research data."""
        manager = DatabaseManager(database_path=temp_db_path)
        manager.initialize()
        
        # Add old and new research
        old_date = datetime.utcnow() - timedelta(days=35)
        new_date = datetime.utcnow() - timedelta(days=5)
        
        with manager.get_session() as session:
            old_research = Research(
                topic="Old Research",
                agent_name="TestAgent",
                started_at=old_date,
                status="completed"
            )
            new_research = Research(
                topic="New Research",
                agent_name="TestAgent",
                started_at=new_date,
                status="completed"
            )
            session.add_all([old_research, new_research])
        
        # Cleanup data older than 30 days
        deleted_count = manager.cleanup_old_data(days_old=30)
        assert deleted_count == 1
        
        # Verify only new research remains
        with manager.get_session() as session:
            remaining = session.query(Research).all()
            assert len(remaining) == 1
            assert remaining[0].topic == "New Research"


class TestSQLiteWriter:
    """Test SQLiteWriter functionality."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def sqlite_writer(self, temp_db_path):
        """Create SQLiteWriter instance."""
        return SQLiteWriter(database_path=temp_db_path)
    
    @pytest.mark.asyncio
    async def test_save_report_basic(self, sqlite_writer):
        """Test basic report saving functionality."""
        content = "# Test Report\n\nThis is a test research report."
        filename = "test_report"
        
        # Prepare research metadata
        research_data = {
            "topic": "Test AI Research",
            "agent_name": "TestAgent",
            "started_at": datetime.utcnow() - timedelta(minutes=5),
            "completed_at": datetime.utcnow(),
            "processing_time": 45.5,
            "executive_summary": "Test summary",
            "key_findings": ["Finding 1", "Finding 2"],
            "detailed_analysis": "Detailed analysis content",
            "total_queries": 2,
            "total_sources": 8,
            "queries": [
                {
                    "query_text": "AI trends 2024",
                    "executed_at": datetime.utcnow(),
                    "max_results": 5,
                    "search_depth": "basic",
                    "include_answer": True,
                    "results_count": 4,
                    "ai_answer": "AI is advancing rapidly",
                    "follow_up_questions": ["What about safety?"],
                    "execution_time": 2.5,
                    "success": True,
                    "sources": [
                        {
                            "title": "AI Article",
                            "url": "https://example.com/ai",
                            "content": "Article content",
                            "score": 0.9,
                            "published_date": "2024-01-01"
                        }
                    ]
                }
            ]
        }
        
        metadata = {"research_data": research_data}
        
        # Save report
        result = await sqlite_writer.save_report(content, filename, metadata)
        
        # Verify result format
        assert result.startswith("research_id:")
        research_id = int(result.split(":")[1])
        
        # Verify data was saved correctly
        research = sqlite_writer.get_research_by_id(research_id)
        assert research is not None
        assert research["topic"] == "Test AI Research"
        assert research["agent_name"] == "TestAgent"
        assert research["total_queries"] == 2
        assert research["total_sources"] == 8
    
    def test_get_research_history(self, sqlite_writer):
        """Test research history retrieval."""
        # First ensure we have no data
        history = sqlite_writer.get_research_history()
        initial_count = len(history)
        
        # Note: This test would need to add data first, but since save_report is async
        # and we're testing the retrieval method specifically, we'll test the empty case
        assert isinstance(history, list)
    
    def test_search_research(self, sqlite_writer):
        """Test research search functionality."""
        results = sqlite_writer.search_research("AI trends")
        assert isinstance(results, list)
        # Empty database should return empty list
        assert len(results) == 0
    
    def test_database_stats(self, sqlite_writer):
        """Test database statistics retrieval."""
        stats = sqlite_writer.get_database_stats()
        assert isinstance(stats, dict)
        assert "total_research_sessions" in stats
        assert "completed_sessions" in stats
        assert "total_queries" in stats
        assert "total_sources" in stats


class TestResearchAnalytics:
    """Test ResearchAnalytics functionality."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def analytics(self, temp_db_path):
        """Create ResearchAnalytics instance."""
        return ResearchAnalytics(database_path=temp_db_path)
    
    def test_get_research_trends_empty(self, analytics):
        """Test research trends with empty database."""
        trends = analytics.get_research_trends(days=30)
        
        assert "period_days" in trends
        assert trends["period_days"] == 30
        assert "total_research_sessions" in trends
        assert trends["total_research_sessions"] == 0
        assert "success_rate_percent" in trends
        assert "daily_research_volume" in trends
        assert "top_topics" in trends
        assert isinstance(trends["daily_research_volume"], list)
        assert isinstance(trends["top_topics"], list)
    
    def test_get_source_analytics_empty(self, analytics):
        """Test source analytics with empty database."""
        source_analytics = analytics.get_source_analytics(days=30)
        
        assert "period_days" in source_analytics
        assert "total_sources" in source_analytics
        assert source_analytics["total_sources"] == 0
        assert "usage_rate_percent" in source_analytics
        assert "top_domains" in source_analytics
        assert isinstance(source_analytics["top_domains"], list)
    
    def test_get_query_patterns_empty(self, analytics):
        """Test query patterns with empty database."""
        query_patterns = analytics.get_query_patterns(days=30)
        
        assert "period_days" in query_patterns
        assert "total_queries" in query_patterns
        assert query_patterns["total_queries"] == 0
        assert "success_rate_percent" in query_patterns
        assert "common_query_terms" in query_patterns
        assert isinstance(query_patterns["common_query_terms"], list)
    
    def test_get_research_summary_not_found(self, analytics):
        """Test research summary for non-existent research."""
        summary = analytics.get_research_summary(research_id=999)
        
        assert "error" in summary
        assert summary["error"] == "Research not found"
    
    def test_get_comparative_analysis_empty(self, analytics):
        """Test comparative analysis with empty database."""
        keywords = ["AI", "machine learning", "deep learning"]
        comparison = analytics.get_comparative_analysis(keywords, days=90)
        
        assert "period_days" in comparison
        assert comparison["period_days"] == 90
        assert "keywords_analyzed" in comparison
        assert comparison["keywords_analyzed"] == keywords
        assert "comparisons" in comparison
        
        # All keywords should have zero results
        for keyword in keywords:
            assert keyword in comparison["comparisons"]
            assert comparison["comparisons"][keyword]["research_count"] == 0