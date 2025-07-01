"""
SQLite implementation of ReportWriter interface with full research tracking.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from urllib.parse import urlparse
import structlog

from ..tools.report_writer import ReportWriter
from .database import DatabaseManager
from .models import Research, Query, Source
from ..utils.llm import normalize_text

logger = structlog.get_logger()


class SQLiteWriter(ReportWriter):
    """SQLite database writer implementation with comprehensive research tracking."""
    
    def __init__(self, database_path: str = "research_history.db"):
        """
        Initialize SQLite writer.
        
        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = Path(database_path)
        self.db_manager = DatabaseManager(database_path=str(self.database_path))
        self.logger = logger.bind(writer="sqlite", db_path=str(self.database_path))
        
        # Initialize database
        self.db_manager.initialize()
        
    async def save_report(self, content: str, filename: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save report to SQLite database and return database record ID.
        
        Args:
            content: The report content to save
            filename: Base filename (used for identification)
            metadata: Research metadata including full research context
            
        Returns:
            Database record identifier (research_id)
        """
        try:
            # Extract research data from metadata
            if not metadata:
                raise ValueError("Metadata required for SQLite writer")
            
            research_data = metadata.get("research_data", {})
            if not research_data:
                raise ValueError("Research data required in metadata")
            
            # Normalize all text content to handle Unicode issues
            content = normalize_text(content)
            
            # Create research record
            with self.db_manager.get_session() as session:
                # Normalize all text fields
                topic = normalize_text(research_data.get("topic", "Unknown Topic"))
                agent_name = normalize_text(research_data.get("agent_name", "Unknown Agent"))
                executive_summary = normalize_text(research_data.get("executive_summary", ""))
                detailed_analysis = normalize_text(research_data.get("detailed_analysis", ""))
                report_path = normalize_text(research_data.get("report_path", ""))
                
                # Normalize focus areas and key findings lists
                focus_areas = research_data.get("focus_areas")
                if focus_areas:
                    focus_areas = [normalize_text(area) for area in focus_areas]
                
                key_findings = research_data.get("key_findings", [])
                if key_findings:
                    key_findings = [normalize_text(finding) for finding in key_findings]
                
                research = Research(
                    topic=topic,
                    focus_areas=focus_areas,
                    agent_name=agent_name,
                    started_at=research_data.get("started_at", datetime.utcnow()),
                    completed_at=research_data.get("completed_at", datetime.utcnow()),
                    processing_time=research_data.get("processing_time", 0.0),
                    status="completed",
                    executive_summary=executive_summary if executive_summary else None,
                    key_findings=key_findings,
                    detailed_analysis=detailed_analysis if detailed_analysis else None,
                    report_content=content,
                    report_path=report_path if report_path else None,
                    total_queries=research_data.get("total_queries", 0),
                    total_sources=research_data.get("total_sources", 0),
                    research_metadata=research_data.get("additional_metadata", {})
                )
                
                session.add(research)
                session.flush()  # Get the ID
                research_id = research.id
                
                # Save queries
                queries_data = research_data.get("queries", [])
                for i, query_data in enumerate(queries_data):
                    # Normalize query text fields
                    query_text = normalize_text(query_data.get("query_text", ""))
                    ai_answer = normalize_text(query_data.get("ai_answer", ""))
                    search_context = normalize_text(query_data.get("search_context", ""))
                    error_message = normalize_text(query_data.get("error_message", ""))
                    
                    # Normalize follow-up questions
                    follow_up_questions = query_data.get("follow_up_questions", [])
                    if follow_up_questions:
                        follow_up_questions = [normalize_text(q) for q in follow_up_questions]
                    
                    query = Query(
                        research_id=research_id,
                        query_text=query_text,
                        query_order=i + 1,
                        executed_at=query_data.get("executed_at", datetime.utcnow()),
                        max_results=query_data.get("max_results", 5),
                        search_depth=query_data.get("search_depth", "basic"),
                        include_answer=query_data.get("include_answer", True),
                        results_count=query_data.get("results_count", 0),
                        ai_answer=ai_answer if ai_answer else None,
                        follow_up_questions=follow_up_questions,
                        search_context=search_context if search_context else None,
                        execution_time=query_data.get("execution_time", 0.0),
                        success=query_data.get("success", True),
                        error_message=error_message if error_message else None
                    )
                    session.add(query)
                    session.flush()  # Get the query ID
                    
                    # Save sources for this query
                    sources_data = query_data.get("sources", [])
                    for source_data in sources_data:
                        # Normalize source text fields
                        title = normalize_text(source_data.get("title", ""))
                        url = source_data.get("url", "")  # Don't normalize URLs
                        content = normalize_text(source_data.get("content", ""))
                        published_date = source_data.get("published_date")
                        
                        source = Source(
                            research_id=research_id,
                            query_id=query.id,
                            title=title,
                            url=url,
                            content=content,
                            relevance_score=source_data.get("score", 0.0),
                            published_date=published_date,
                            retrieved_at=datetime.utcnow(),
                            content_length=len(content),
                            used_in_analysis=True  # Assume all retrieved sources were used
                        )
                        source.extract_domain()  # Extract domain from URL
                        session.add(source)
                
                session.commit()
                
                self.logger.info(
                    "Research saved to database",
                    research_id=research_id,
                    topic=research.topic,
                    queries=len(queries_data),
                    sources=research.total_sources
                )
                
                return f"research_id:{research_id}"
                
        except Exception as e:
            self.logger.error("Failed to save research to database", error=str(e))
            raise RuntimeError(f"Failed to save research to database: {str(e)}") from e
    
    def get_research_by_id(self, research_id: int) -> Optional[Dict[str, Any]]:
        """Get research record by ID."""
        try:
            with self.db_manager.get_session() as session:
                research = session.query(Research).filter(Research.id == research_id).first()
                if research:
                    return research.to_dict()
                return None
        except Exception as e:
            self.logger.error("Failed to get research by ID", research_id=research_id, error=str(e))
            return None
    
    def get_research_history(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get research history with pagination."""
        try:
            with self.db_manager.get_session() as session:
                research_list = session.query(Research).order_by(
                    Research.started_at.desc()
                ).offset(offset).limit(limit).all()
                
                return [r.to_dict() for r in research_list]
        except Exception as e:
            self.logger.error("Failed to get research history", error=str(e))
            return []
    
    def search_research(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search research by topic or content."""
        try:
            with self.db_manager.get_session() as session:
                research_list = session.query(Research).filter(
                    Research.topic.contains(query) |
                    Research.detailed_analysis.contains(query) |
                    Research.executive_summary.contains(query)
                ).order_by(Research.started_at.desc()).limit(limit).all()
                
                return [r.to_dict() for r in research_list]
        except Exception as e:
            self.logger.error("Failed to search research", query=query, error=str(e))
            return []
    
    def get_research_with_details(self, research_id: int) -> Optional[Dict[str, Any]]:
        """Get complete research record with queries and sources."""
        try:
            with self.db_manager.get_session() as session:
                research = session.query(Research).filter(Research.id == research_id).first()
                if not research:
                    return None
                
                # Get queries with sources
                queries = session.query(Query).filter(Query.research_id == research_id).order_by(Query.query_order).all()
                
                research_dict = research.to_dict()
                research_dict["queries"] = []
                
                for query in queries:
                    query_dict = query.to_dict()
                    
                    # Get sources for this query
                    sources = session.query(Source).filter(Source.query_id == query.id).all()
                    query_dict["sources"] = [s.to_dict() for s in sources]
                    
                    research_dict["queries"].append(query_dict)
                
                return research_dict
                
        except Exception as e:
            self.logger.error("Failed to get research with details", research_id=research_id, error=str(e))
            return None
    
    def delete_research(self, research_id: int) -> bool:
        """Delete research record and all associated data."""
        try:
            with self.db_manager.get_session() as session:
                research = session.query(Research).filter(Research.id == research_id).first()
                if research:
                    session.delete(research)  # Cascades to queries and sources
                    session.commit()
                    self.logger.info("Research deleted", research_id=research_id)
                    return True
                return False
        except Exception as e:
            self.logger.error("Failed to delete research", research_id=research_id, error=str(e))
            return False
    
    def update_research_status(self, research_id: int, status: str, error_message: Optional[str] = None) -> bool:
        """Update research status (for tracking in-progress research)."""
        try:
            with self.db_manager.get_session() as session:
                research = session.query(Research).filter(Research.id == research_id).first()
                if research:
                    research.status = status
                    if error_message:
                        research.error_message = error_message
                    if status == "completed":
                        research.completed_at = datetime.utcnow()
                    session.commit()
                    return True
                return False
        except Exception as e:
            self.logger.error("Failed to update research status", research_id=research_id, error=str(e))
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return self.db_manager.get_database_stats()
    
    def backup_database(self, backup_path: str) -> bool:
        """Create database backup."""
        return self.db_manager.backup_database(backup_path)
    
    def cleanup_old_data(self, days_old: int = 30) -> int:
        """Clean up old research data."""
        return self.db_manager.cleanup_old_data(days_old)