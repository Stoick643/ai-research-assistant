"""
Tests for the ReportWriter module.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

from src.tools.report_writer import (
    ReportWriter, MarkdownWriter, SQLiteWriter, ReportFormatter
)


class TestMarkdownWriter:
    """Test suite for MarkdownWriter."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def markdown_writer(self, temp_dir):
        """Create MarkdownWriter instance for testing."""
        return MarkdownWriter(output_dir=temp_dir)
    
    @pytest.mark.asyncio
    async def test_save_report_basic(self, markdown_writer, temp_dir):
        """Test basic report saving functionality."""
        content = "# Test Report\n\nThis is a test report."
        filename = "test_report"
        
        result_path = await markdown_writer.save_report(content, filename)
        
        # Check file was created
        assert Path(result_path).exists()
        assert Path(result_path).parent == Path(temp_dir)
        assert filename in Path(result_path).name
        assert Path(result_path).suffix == ".md"
        
        # Check content
        with open(result_path, 'r') as f:
            saved_content = f.read()
        assert saved_content == content
    
    @pytest.mark.asyncio
    async def test_save_report_with_metadata(self, markdown_writer, temp_dir):
        """Test report saving with metadata."""
        content = "# Test Report\n\nThis is a test report."
        filename = "test_report"
        metadata = {
            "author": "Test Author",
            "query_count": 5,
            "processing_time": 30.5,
            "created_date": datetime(2024, 1, 1, 12, 0, 0)
        }
        
        result_path = await markdown_writer.save_report(content, filename, metadata)
        
        # Check content includes metadata
        with open(result_path, 'r') as f:
            saved_content = f.read()
        
        assert "## Report Metadata" in saved_content
        assert "**Author**: Test Author" in saved_content
        assert "**Query Count**: 5" in saved_content
        assert "**Processing Time**: 30.5" in saved_content
        assert "**Created Date**: 2024-01-01 12:00:00" in saved_content
    
    def test_sanitize_filename(self, markdown_writer):
        """Test filename sanitization."""
        # Test invalid characters
        result = markdown_writer._sanitize_filename("test<>:file/name|?.txt")
        assert result == "test___file_name____txt"
        
        # Test spaces
        result = markdown_writer._sanitize_filename("test   file   name")
        assert result == "test_file_name"
        
        # Test long filename
        long_name = "a" * 100
        result = markdown_writer._sanitize_filename(long_name)
        assert len(result) <= 50
        
        # Test lowercase conversion
        result = markdown_writer._sanitize_filename("TEST FILE NAME")
        assert result == "test_file_name"
    
    def test_add_metadata_to_content(self, markdown_writer):
        """Test metadata addition to content."""
        content = "# Test Report\n\nContent here."
        metadata = {
            "author": "Test Author",
            "date": datetime(2024, 1, 1),
            "tags": ["tag1", "tag2"]
        }
        
        result = markdown_writer._add_metadata_to_content(content, metadata)
        
        assert "## Report Metadata" in result
        assert "**Author**: Test Author" in result
        assert "**Date**: 2024-01-01 00:00:00" in result
        assert "**Tags**: ['tag1', 'tag2']" in result
    
    def test_add_metadata_replace_existing(self, markdown_writer):
        """Test metadata replacement when metadata section already exists."""
        content = "# Test Report\n\nContent here.\n\n## Metadata\n- Old metadata"
        metadata = {"author": "New Author"}
        
        result = markdown_writer._add_metadata_to_content(content, metadata)
        
        assert "## Report Metadata" in result
        assert "**Author**: New Author" in result
        assert "Old metadata" not in result
    
    @pytest.mark.asyncio
    async def test_save_report_create_directory(self, temp_dir):
        """Test that save_report creates directory if it doesn't exist."""
        non_existent_dir = Path(temp_dir) / "new_directory"
        writer = MarkdownWriter(output_dir=str(non_existent_dir))
        
        content = "# Test Report"
        filename = "test"
        
        result_path = await writer.save_report(content, filename)
        
        assert Path(result_path).exists()
        assert Path(result_path).parent == non_existent_dir
    
    @pytest.mark.asyncio
    async def test_save_report_file_error(self, markdown_writer):
        """Test error handling when file save fails."""
        with patch('pathlib.Path.write_text', side_effect=IOError("Write failed")):
            with pytest.raises(RuntimeError, match="Failed to save report: Write failed"):
                await markdown_writer.save_report("content", "filename")


class TestSQLiteWriter:
    """Test suite for SQLiteWriter."""
    
    def test_init(self):
        """Test SQLiteWriter initialization."""
        writer = SQLiteWriter("test.db")
        assert writer.db_path == Path("test.db")
    
    @pytest.mark.asyncio
    async def test_save_report_not_implemented(self):
        """Test that SQLiteWriter raises NotImplementedError."""
        writer = SQLiteWriter()
        
        with pytest.raises(NotImplementedError, match="SQLite writer will be implemented"):
            await writer.save_report("content", "filename")


class TestReportFormatter:
    """Test suite for ReportFormatter."""
    
    def test_format_research_report(self):
        """Test research report formatting."""
        topic = "AI Trends 2025"
        executive_summary = "AI is advancing rapidly in 2025."
        key_findings = [
            "Generative AI is mainstream",
            "Edge AI is growing",
            "Safety concerns are increasing"
        ]
        detailed_analysis = "Detailed analysis of AI trends..."
        sources = [
            {"title": "AI Report 2025", "url": "https://example.com/ai-report"},
            {"title": "Tech Trends", "url": "https://example.com/tech-trends"}
        ]
        query_count = 5
        processing_time = 45.7
        
        result = ReportFormatter.format_research_report(
            topic=topic,
            executive_summary=executive_summary,
            key_findings=key_findings,
            detailed_analysis=detailed_analysis,
            sources=sources,
            query_count=query_count,
            processing_time=processing_time
        )
        
        # Check structure
        assert f"# Research Report: {topic}" in result
        assert "## Executive Summary" in result
        assert "## Key Findings" in result
        assert "## Detailed Analysis" in result
        assert "## Sources" in result
        assert "## Metadata" in result
        
        # Check content
        assert executive_summary in result
        assert detailed_analysis in result
        assert "**Finding 1**: Generative AI is mainstream" in result
        assert "**Finding 2**: Edge AI is growing" in result
        assert "[AI Report 2025](https://example.com/ai-report)" in result
        assert "**Query Count**: 5" in result
        assert "45.7 seconds" in result
    
    def test_format_research_report_time_formatting(self):
        """Test time formatting in research report."""
        # Test seconds
        result = ReportFormatter.format_research_report(
            topic="Test",
            executive_summary="Summary",
            key_findings=["Finding"],
            detailed_analysis="Analysis",
            sources=[],
            query_count=1,
            processing_time=30.5
        )
        assert "30.5 seconds" in result
        
        # Test minutes and seconds
        result = ReportFormatter.format_research_report(
            topic="Test",
            executive_summary="Summary",
            key_findings=["Finding"],
            detailed_analysis="Analysis",
            sources=[],
            query_count=1,
            processing_time=125.7  # 2 minutes 5 seconds
        )
        assert "2m 5s" in result
    
    def test_format_research_report_empty_sources(self):
        """Test research report formatting with empty sources."""
        result = ReportFormatter.format_research_report(
            topic="Test Topic",
            executive_summary="Summary",
            key_findings=["Finding 1"],
            detailed_analysis="Analysis",
            sources=[],
            query_count=0,
            processing_time=10.0
        )
        
        assert "# Research Report: Test Topic" in result
        assert "## Sources" in result
        # Should have empty sources section
        lines = result.split('\n')
        sources_index = next(i for i, line in enumerate(lines) if line == "## Sources")
        metadata_index = next(i for i, line in enumerate(lines) if line == "## Metadata")
        
        # Check that sources section is empty (only contains newlines)
        sources_section = lines[sources_index + 1:metadata_index]
        non_empty_lines = [line for line in sources_section if line.strip()]
        assert len(non_empty_lines) == 0