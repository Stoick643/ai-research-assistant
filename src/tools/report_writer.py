"""
Report writer interface and implementations for generating structured reports.
"""

import os
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import structlog

logger = structlog.get_logger()


class ReportWriter(ABC):
    """Abstract base class for report writers."""
    
    @abstractmethod
    async def save_report(self, content: str, filename: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save report and return file path.
        
        Args:
            content: The report content to save
            filename: Desired filename (without extension)
            metadata: Optional metadata to include with the report
            
        Returns:
            Full path to the saved report file
        """
        pass


class MarkdownWriter(ReportWriter):
    """Markdown file writer implementation."""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.logger = logger.bind(writer="markdown")
        
    async def save_report(self, content: str, filename: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save markdown report to file.
        
        Args:
            content: The markdown content to save
            filename: Base filename (without extension)
            metadata: Optional metadata to include in the report
            
        Returns:
            Full path to the saved markdown file
        """
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = self._sanitize_filename(filename)
        full_filename = f"{safe_filename}_{timestamp}.md"
        file_path = self.output_dir / full_filename
        
        # Add metadata to content if provided
        if metadata:
            content = self._add_metadata_to_content(content, metadata)
        
        # Write file asynchronously
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: file_path.write_text(content, encoding='utf-8')
            )
            
            self.logger.info(
                "Report saved successfully",
                filename=full_filename,
                path=str(file_path),
                size=len(content)
            )
            
            return str(file_path)
            
        except Exception as e:
            self.logger.error(
                "Failed to save report",
                filename=full_filename,
                error=str(e)
            )
            raise RuntimeError(f"Failed to save report: {str(e)}") from e
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be filesystem-safe."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove extra spaces and convert to lowercase
        filename = '_'.join(filename.split()).lower()
        
        # Limit length
        if len(filename) > 50:
            filename = filename[:50]
        
        return filename
    
    def _add_metadata_to_content(self, content: str, metadata: Dict[str, Any]) -> str:
        """Add metadata section to the report content."""
        metadata_section = "\n\n## Report Metadata\n\n"
        
        for key, value in metadata.items():
            if isinstance(value, datetime):
                value = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, (list, dict)):
                value = str(value)
            
            metadata_section += f"- **{key.replace('_', ' ').title()}**: {value}\n"
        
        # Add metadata before any existing metadata section or at the end
        if "## Metadata" in content:
            # Replace existing metadata section
            parts = content.split("## Metadata")
            if len(parts) > 1:
                # Find the end of the metadata section
                remaining_content = parts[1]
                next_section_start = remaining_content.find("\n## ")
                if next_section_start != -1:
                    content = parts[0] + metadata_section + remaining_content[next_section_start:]
                else:
                    content = parts[0] + metadata_section
            else:
                content = content + metadata_section
        else:
            content = content + metadata_section
        
        return content


class SQLiteWriter(ReportWriter):
    """SQLite database writer implementation (future enhancement)."""
    
    def __init__(self, db_path: str = "reports.db"):
        self.db_path = Path(db_path)
        self.logger = logger.bind(writer="sqlite")
        
    async def save_report(self, content: str, filename: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save report to SQLite database.
        
        Note: This is a placeholder implementation for future enhancement.
        """
        # TODO: Implement SQLite storage
        # - Create tables if not exists
        # - Insert report with metadata
        # - Return database record ID or path
        
        self.logger.warning("SQLite writer not yet implemented")
        raise NotImplementedError("SQLite writer will be implemented in future version")


class ReportFormatter:
    """Utility class for formatting structured reports."""
    
    @staticmethod
    def format_research_report(
        topic: str,
        executive_summary: str,
        key_findings: list,
        detailed_analysis: str,
        sources: list,
        query_count: int,
        processing_time: float
    ) -> str:
        """
        Format a research report in the standard template.
        
        Args:
            topic: Research topic
            executive_summary: Brief overview of findings
            key_findings: List of key findings
            detailed_analysis: Detailed analysis content
            sources: List of source dictionaries with 'title' and 'url' keys
            query_count: Number of queries performed
            processing_time: Time taken for research in seconds
            
        Returns:
            Formatted markdown report
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format key findings
        findings_section = ""
        for i, finding in enumerate(key_findings, 1):
            findings_section += f"- **Finding {i}**: {finding}\n"
        
        # Format sources
        sources_section = ""
        for i, source in enumerate(sources, 1):
            title = source.get('title', 'Unknown Title')
            url = source.get('url', '#')
            sources_section += f"{i}. [{title}]({url})\n"
        
        # Format processing time
        if processing_time < 60:
            time_str = f"{processing_time:.1f} seconds"
        else:
            minutes = int(processing_time // 60)
            seconds = int(processing_time % 60)
            time_str = f"{minutes}m {seconds}s"
        
        report = f"""# Research Report: {topic}

## Executive Summary

{executive_summary}

## Key Findings

{findings_section}

## Detailed Analysis

{detailed_analysis}

## Sources

{sources_section}

## Metadata

- **Research Date**: {timestamp}
- **Query Count**: {query_count}
- **Processing Time**: {time_str}
"""
        
        return report