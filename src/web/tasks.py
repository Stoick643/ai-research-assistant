"""
Celery tasks for asynchronous research processing.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from celery import Celery
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Celery app will be created when needed
celery = None
flask_app = None


@celery.task(bind=True)
def conduct_research_task(self, research_id: int, task_data: Dict[str, Any]):
    """
    Conduct research asynchronously using existing research agents.
    
    Args:
        research_id: Database ID of the research record
        task_data: Research parameters
    """
    
    with flask_app.app_context():
        try:
            # Get research record
            research = Research.query.get(research_id)
            if not research:
                raise ValueError(f"Research with ID {research_id} not found")
            
            # Update status
            research.status = 'in_progress'
            db.session.commit()
            
            # Initialize LLM client
            openai_key = flask_app.config.get('OPENAI_API_KEY')
            if not openai_key:
                raise ValueError("OPENAI_API_KEY not configured")
            
            llm_client = create_llm_client("openai", api_key=openai_key)
            
            # Initialize tools
            tavily_key = flask_app.config.get('TAVILY_API_KEY')
            if not tavily_key:
                raise ValueError("TAVILY_API_KEY not configured")
            
            web_search_tool = WebSearchTool(api_key=tavily_key)
            report_writer = MarkdownWriter(output_dir=flask_app.config.get('REPORTS_DIR', 'reports'))
            sqlite_writer = SQLiteWriter(db_path="research_history.db")
            
            # Choose agent based on translation requirements
            if research.translation_enabled and len(research.translated_languages) > 1:
                agent = MultiLanguageResearchAgent(
                    name="WebMultiLangResearcher",
                    llm_client=llm_client,
                    web_search_tool=web_search_tool,
                    report_writer=report_writer,
                    sqlite_writer=sqlite_writer,
                    enable_database_tracking=True,
                    default_language='en',
                    target_languages=research.translated_languages,
                    enable_translation=True
                )
                
                # Conduct multilingual research
                import asyncio
                result = asyncio.run(agent.conduct_multilang_research(
                    topic=task_data['topic'],
                    focus_areas=task_data.get('focus_areas'),
                    source_language=task_data.get('source_language'),
                    target_languages=task_data.get('target_languages', ['en']),
                    max_queries=task_data.get('max_queries', 5),
                    search_depth=task_data.get('search_depth', 'basic')
                ))
            else:
                agent = ResearchAgent(
                    name="WebResearcher",
                    llm_client=llm_client,
                    web_search_tool=web_search_tool,
                    report_writer=report_writer,
                    sqlite_writer=sqlite_writer,
                    enable_database_tracking=True
                )
                
                # Conduct standard research
                result = asyncio.run(agent.conduct_research(
                    topic=task_data['topic'],
                    focus_areas=task_data.get('focus_areas'),
                    max_queries=task_data.get('max_queries', 5)
                ))
            
            # Update research record with results
            research.completed_at = datetime.utcnow()
            research.processing_time = result.get('processing_time', 0)
            research.status = 'completed'
            research.executive_summary = result.get('executive_summary', '')
            research.key_findings = result.get('key_findings', [])
            research.detailed_analysis = result.get('detailed_analysis', '')
            research.report_content = result.get('report_content', '')
            research.report_path = result.get('report_path', '')
            research.total_queries = result.get('total_queries', 0)
            research.total_sources = result.get('total_sources', 0)
            
            # Store research metadata
            research.research_metadata.update({
                'completed_via': 'web_interface',
                'agent_type': 'MultiLanguageResearchAgent' if research.translation_enabled else 'ResearchAgent',
                'result_metadata': result.get('metadata', {})
            })
            
            # Save translations if available
            if 'translations' in result and result['translations']:
                for lang_code, translation_data in result['translations'].items():
                    if 'error' not in translation_data:
                        translation = Translation(
                            research_id=research.id,
                            target_language=lang_code,
                            source_language='en',
                            translated_summary=translation_data.get('executive_summary', {}).get('text', ''),
                            translated_findings=translation_data.get('key_findings', []),
                            translated_analysis=translation_data.get('detailed_analysis', ''),
                            translation_provider='google',  # Default provider
                            translated_at=datetime.utcnow(),
                            processing_time=translation_data.get('processing_time', 0),
                            character_count=len(str(translation_data)),
                            confidence_score=translation_data.get('confidence_score', 0.0)
                        )
                        db.session.add(translation)
            
            db.session.commit()
            
            return {
                'status': 'completed',
                'research_id': research_id,
                'message': 'Research completed successfully'
            }
            
        except Exception as e:
            # Update research record with error
            with flask_app.app_context():
                research = Research.query.get(research_id)
                if research:
                    research.status = 'failed'
                    research.error_message = str(e)
                    research.completed_at = datetime.utcnow()
                    db.session.commit()
            
            # Re-raise exception for Celery error handling
            raise


@celery.task
def cleanup_old_research(days_old: int = 90):
    """
    Clean up old research records and associated files.
    
    Args:
        days_old: Delete research older than this many days
    """
    
    with flask_app.app_context():
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Find old research records
        old_research = Research.query.filter(
            Research.completed_at < cutoff_date,
            Research.status.in_(['completed', 'failed'])
        ).all()
        
        deleted_count = 0
        for research in old_research:
            # Delete associated files if they exist
            if research.report_path and os.path.exists(research.report_path):
                try:
                    os.remove(research.report_path)
                except OSError:
                    pass  # File might already be deleted
            
            # Delete database record (cascades to related records)
            db.session.delete(research)
            deleted_count += 1
        
        db.session.commit()
        
        return {
            'status': 'completed',
            'deleted_count': deleted_count,
            'message': f'Cleaned up {deleted_count} old research records'
        }


@celery.task
def generate_analytics_report():
    """Generate analytics report for system performance."""
    
    with flask_app.app_context():
        from datetime import timedelta
        from sqlalchemy import func
        
        # Calculate various statistics
        total_research = Research.query.count()
        completed_research = Research.query.filter_by(status='completed').count()
        failed_research = Research.query.filter_by(status='failed').count()
        
        # Recent activity (last 30 days)
        month_ago = datetime.utcnow() - timedelta(days=30)
        recent_research = Research.query.filter(
            Research.started_at >= month_ago
        ).count()
        
        # Average processing time
        avg_processing_time = db.session.query(
            func.avg(Research.processing_time)
        ).filter(
            Research.status == 'completed',
            Research.processing_time.isnot(None)
        ).scalar()
        
        # Language distribution
        language_stats = db.session.query(
            Research.research_language,
            func.count(Research.id)
        ).group_by(Research.research_language).all()
        
        # Translation usage
        translation_enabled_count = Research.query.filter_by(
            translation_enabled=True
        ).count()
        
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'totals': {
                'total_research': total_research,
                'completed_research': completed_research,
                'failed_research': failed_research,
                'success_rate': round((completed_research / total_research * 100) if total_research > 0 else 0, 1)
            },
            'recent_activity': {
                'last_30_days': recent_research
            },
            'performance': {
                'avg_processing_time': round(avg_processing_time, 2) if avg_processing_time else 0
            },
            'language_distribution': [
                {'language': lang, 'count': count} for lang, count in language_stats
            ],
            'translation_usage': {
                'enabled_count': translation_enabled_count,
                'enabled_percentage': round((translation_enabled_count / total_research * 100) if total_research > 0 else 0, 1)
            }
        }
        
        return report