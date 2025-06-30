"""
Research analytics and insights from SQLite database.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func, desc, asc
from sqlalchemy.orm import Session
import structlog

from .database import DatabaseManager
from .models import Research, Query, Source

logger = structlog.get_logger()


class ResearchAnalytics:
    """Analytics engine for research history and patterns."""
    
    def __init__(self, database_path: str = "research_history.db"):
        """
        Initialize analytics engine.
        
        Args:
            database_path: Path to SQLite database file
        """
        self.db_manager = DatabaseManager(database_path=database_path)
        self.db_manager.initialize()
        self.logger = logger.bind(component="analytics")
    
    def get_research_trends(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze research trends over specified time period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            with self.db_manager.get_session() as session:
                # Research volume by day
                daily_research = session.query(
                    func.date(Research.started_at).label("date"),
                    func.count(Research.id).label("count")
                ).filter(
                    Research.started_at >= cutoff_date
                ).group_by(
                    func.date(Research.started_at)
                ).order_by(asc("date")).all()
                
                # Most researched topics
                topic_frequencies = session.query(
                    Research.topic,
                    func.count(Research.id).label("frequency")
                ).filter(
                    Research.started_at >= cutoff_date
                ).group_by(Research.topic).order_by(desc("frequency")).limit(10).all()
                
                # Average processing times
                avg_processing_time = session.query(
                    func.avg(Research.processing_time)
                ).filter(
                    Research.started_at >= cutoff_date,
                    Research.processing_time.isnot(None)
                ).scalar()
                
                # Success rate
                total_research = session.query(Research).filter(
                    Research.started_at >= cutoff_date
                ).count()
                
                successful_research = session.query(Research).filter(
                    Research.started_at >= cutoff_date,
                    Research.status == "completed"
                ).count()
                
                success_rate = (successful_research / total_research * 100) if total_research > 0 else 0
                
                return {
                    "period_days": days,
                    "total_research_sessions": total_research,
                    "successful_sessions": successful_research,
                    "success_rate_percent": round(success_rate, 2),
                    "average_processing_time_seconds": round(avg_processing_time or 0, 2),
                    "daily_research_volume": [
                        {"date": str(date), "count": count} for date, count in daily_research
                    ],
                    "top_topics": [
                        {"topic": topic, "frequency": freq} for topic, freq in topic_frequencies
                    ]
                }
                
        except Exception as e:
            self.logger.error("Failed to analyze research trends", error=str(e))
            return {"error": str(e)}
    
    def get_source_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze source patterns and quality metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with source analytics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            with self.db_manager.get_session() as session:
                # Top domains by frequency
                top_domains = session.query(
                    Source.domain,
                    func.count(Source.id).label("count"),
                    func.avg(Source.relevance_score).label("avg_score")
                ).join(Research).filter(
                    Research.started_at >= cutoff_date,
                    Source.domain.isnot(None),
                    Source.domain != "unknown"
                ).group_by(Source.domain).order_by(desc("count")).limit(15).all()
                
                # Average relevance scores by domain
                domain_quality = session.query(
                    Source.domain,
                    func.avg(Source.relevance_score).label("avg_score"),
                    func.count(Source.id).label("source_count")
                ).join(Research).filter(
                    Research.started_at >= cutoff_date,
                    Source.domain.isnot(None),
                    Source.domain != "unknown",
                    Source.relevance_score.isnot(None)
                ).group_by(Source.domain).having(
                    func.count(Source.id) >= 3  # At least 3 sources for meaningful average
                ).order_by(desc("avg_score")).limit(10).all()
                
                # Source usage statistics
                total_sources = session.query(Source).join(Research).filter(
                    Research.started_at >= cutoff_date
                ).count()
                
                used_sources = session.query(Source).join(Research).filter(
                    Research.started_at >= cutoff_date,
                    Source.used_in_analysis == True
                ).count()
                
                usage_rate = (used_sources / total_sources * 100) if total_sources > 0 else 0
                
                # Average content length
                avg_content_length = session.query(
                    func.avg(Source.content_length)
                ).join(Research).filter(
                    Research.started_at >= cutoff_date,
                    Source.content_length.isnot(None)
                ).scalar()
                
                return {
                    "period_days": days,
                    "total_sources": total_sources,
                    "sources_used_in_analysis": used_sources,
                    "usage_rate_percent": round(usage_rate, 2),
                    "average_content_length": round(avg_content_length or 0, 0),
                    "top_domains": [
                        {
                            "domain": domain,
                            "source_count": count,
                            "average_relevance_score": round(float(avg_score or 0), 3)
                        }
                        for domain, count, avg_score in top_domains
                    ],
                    "highest_quality_domains": [
                        {
                            "domain": domain,
                            "average_relevance_score": round(float(avg_score), 3),
                            "source_count": count
                        }
                        for domain, avg_score, count in domain_quality
                    ]
                }
                
        except Exception as e:
            self.logger.error("Failed to analyze source patterns", error=str(e))
            return {"error": str(e)}
    
    def get_query_patterns(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze search query patterns and effectiveness.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with query analytics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            with self.db_manager.get_session() as session:
                # Query success rates
                total_queries = session.query(Query).join(Research).filter(
                    Research.started_at >= cutoff_date
                ).count()
                
                successful_queries = session.query(Query).join(Research).filter(
                    Research.started_at >= cutoff_date,
                    Query.success == True
                ).count()
                
                query_success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0
                
                # Average results per query
                avg_results = session.query(
                    func.avg(Query.results_count)
                ).join(Research).filter(
                    Research.started_at >= cutoff_date,
                    Query.success == True
                ).scalar()
                
                # Most common query terms (simplified)
                common_terms = session.query(
                    Query.query_text
                ).join(Research).filter(
                    Research.started_at >= cutoff_date,
                    Query.success == True
                ).limit(100).all()
                
                # Extract common words (basic analysis)
                word_freq = {}
                for (query_text,) in common_terms:
                    words = query_text.lower().split()
                    for word in words:
                        if len(word) > 3 and word.isalpha():  # Skip short and non-alphabetic words
                            word_freq[word] = word_freq.get(word, 0) + 1
                
                top_terms = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:15]
                
                # Search depth distribution
                depth_distribution = session.query(
                    Query.search_depth,
                    func.count(Query.id).label("count")
                ).join(Research).filter(
                    Research.started_at >= cutoff_date
                ).group_by(Query.search_depth).all()
                
                # Average execution time
                avg_execution_time = session.query(
                    func.avg(Query.execution_time)
                ).join(Research).filter(
                    Research.started_at >= cutoff_date,
                    Query.execution_time.isnot(None)
                ).scalar()
                
                return {
                    "period_days": days,
                    "total_queries": total_queries,
                    "successful_queries": successful_queries,
                    "success_rate_percent": round(query_success_rate, 2),
                    "average_results_per_query": round(avg_results or 0, 1),
                    "average_execution_time_seconds": round(avg_execution_time or 0, 3),
                    "search_depth_distribution": [
                        {"depth": depth, "count": count} for depth, count in depth_distribution
                    ],
                    "common_query_terms": [
                        {"term": term, "frequency": freq} for term, freq in top_terms
                    ]
                }
                
        except Exception as e:
            self.logger.error("Failed to analyze query patterns", error=str(e))
            return {"error": str(e)}
    
    def get_research_summary(self, research_id: int) -> Dict[str, Any]:
        """
        Get detailed summary for a specific research session.
        
        Args:
            research_id: Research session ID
            
        Returns:
            Dictionary with research summary
        """
        try:
            with self.db_manager.get_session() as session:
                research = session.query(Research).filter(Research.id == research_id).first()
                if not research:
                    return {"error": "Research not found"}
                
                # Get query performance
                queries = session.query(Query).filter(Query.research_id == research_id).all()
                
                # Get source distribution by domain
                source_domains = session.query(
                    Source.domain,
                    func.count(Source.id).label("count"),
                    func.avg(Source.relevance_score).label("avg_score")
                ).filter(
                    Source.research_id == research_id,
                    Source.domain.isnot(None)
                ).group_by(Source.domain).all()
                
                # Calculate metrics
                total_execution_time = sum(q.execution_time or 0 for q in queries)
                successful_queries = sum(1 for q in queries if q.success)
                total_results = sum(q.results_count or 0 for q in queries)
                
                return {
                    "research_id": research_id,
                    "topic": research.topic,
                    "status": research.status,
                    "started_at": research.started_at.isoformat() if research.started_at else None,
                    "completed_at": research.completed_at.isoformat() if research.completed_at else None,
                    "processing_time_seconds": research.processing_time,
                    "total_queries": len(queries),
                    "successful_queries": successful_queries,
                    "total_search_results": total_results,
                    "total_query_execution_time": round(total_execution_time, 3),
                    "source_domains": [
                        {
                            "domain": domain,
                            "source_count": count,
                            "average_relevance": round(float(avg_score or 0), 3)
                        }
                        for domain, count, avg_score in source_domains
                    ],
                    "queries": [
                        {
                            "order": q.query_order,
                            "text": q.query_text,
                            "success": q.success,
                            "results_count": q.results_count,
                            "execution_time": q.execution_time
                        }
                        for q in queries
                    ]
                }
                
        except Exception as e:
            self.logger.error("Failed to get research summary", research_id=research_id, error=str(e))
            return {"error": str(e)}
    
    def get_comparative_analysis(self, topic_keywords: List[str], days: int = 90) -> Dict[str, Any]:
        """
        Compare research patterns across different topics.
        
        Args:
            topic_keywords: List of keywords to compare
            days: Number of days to analyze
            
        Returns:
            Dictionary with comparative analysis
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            comparisons = {}
            
            with self.db_manager.get_session() as session:
                for keyword in topic_keywords:
                    # Find research sessions containing this keyword
                    related_research = session.query(Research).filter(
                        Research.started_at >= cutoff_date,
                        Research.topic.contains(keyword)
                    ).all()
                    
                    if related_research:
                        # Calculate metrics for this topic
                        processing_times = [r.processing_time for r in related_research if r.processing_time]
                        total_queries = sum(r.total_queries or 0 for r in related_research)
                        total_sources = sum(r.total_sources or 0 for r in related_research)
                        successful = sum(1 for r in related_research if r.status == "completed")
                        
                        comparisons[keyword] = {
                            "research_count": len(related_research),
                            "success_rate_percent": round((successful / len(related_research)) * 100, 2),
                            "average_processing_time": round(sum(processing_times) / len(processing_times), 2) if processing_times else 0,
                            "average_queries_per_research": round(total_queries / len(related_research), 1),
                            "average_sources_per_research": round(total_sources / len(related_research), 1)
                        }
                    else:
                        comparisons[keyword] = {
                            "research_count": 0,
                            "success_rate_percent": 0,
                            "average_processing_time": 0,
                            "average_queries_per_research": 0,
                            "average_sources_per_research": 0
                        }
                
                return {
                    "period_days": days,
                    "keywords_analyzed": topic_keywords,
                    "comparisons": comparisons
                }
                
        except Exception as e:
            self.logger.error("Failed to perform comparative analysis", error=str(e))
            return {"error": str(e)}