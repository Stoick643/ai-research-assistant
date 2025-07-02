"""
API blueprint for JSON endpoints and AJAX functionality.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from sqlalchemy import desc, func

from ..models import Research, Query, Source, Translation, db

api_bp = Blueprint('api', __name__)


@api_bp.route('/research/status/<int:research_id>')
def research_status(research_id):
    """Get research status and progress information."""
    research = Research.query.get_or_404(research_id)
    
    # Calculate progress percentage
    progress = 0
    if research.status == 'completed':
        progress = 100
    elif research.status == 'failed':
        progress = 0
    else:
        # Estimate progress based on queries completed
        total_queries = research.research_metadata.get('max_queries', 5) if research.research_metadata else 5
        completed_queries = len(research.queries)
        progress = min(int((completed_queries / total_queries) * 80), 80)  # Max 80% until completion
    
    # Get current stage
    stage = 'Starting'
    if research.queries:
        stage = 'Searching and analyzing'
    if research.executive_summary:
        stage = 'Generating report'
    if research.status == 'completed':
        stage = 'Completed'
    elif research.status == 'failed':
        stage = 'Failed'
    
    return jsonify({
        'id': research.id,
        'status': research.status,
        'progress': progress,
        'stage': stage,
        'started_at': research.started_at.isoformat() if research.started_at else None,
        'completed_at': research.completed_at.isoformat() if research.completed_at else None,
        'processing_time': research.processing_time,
        'total_queries': research.total_queries,
        'total_sources': research.total_sources,
        'error_message': research.error_message,
        'has_results': bool(research.executive_summary),
        'translation_enabled': research.translation_enabled,
        'translated_languages': research.translated_languages
    })


@api_bp.route('/research/list')
def research_list():
    """Get paginated list of research with optional filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status', '')
    search = request.args.get('search', '')
    language = request.args.get('language', '')
    
    # Build query
    query = Research.query
    
    if status:
        query = query.filter(Research.status == status)
    
    if search:
        query = query.filter(Research.topic.contains(search))
    
    if language:
        query = query.filter(Research.research_language == language)
    
    # Order by most recent
    query = query.order_by(desc(Research.started_at))
    
    # Paginate
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return jsonify({
        'research': [research.to_dict() for research in pagination.items],
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next
        }
    })


@api_bp.route('/research/<int:research_id>/queries')
def research_queries(research_id):
    """Get queries for a specific research."""
    research = Research.query.get_or_404(research_id)
    queries = Query.query.filter_by(research_id=research_id).order_by(Query.query_order).all()
    
    return jsonify({
        'research_id': research_id,
        'queries': [{
            'id': query.id,
            'query_text': query.query_text,
            'query_language': query.query_language,
            'query_order': query.query_order,
            'executed_at': query.executed_at.isoformat() if query.executed_at else None,
            'processing_time': query.processing_time,
            'results_count': query.results_count,
            'success': query.success,
            'error_message': query.error_message,
            'search_provider': query.search_provider
        } for query in queries]
    })


@api_bp.route('/research/<int:research_id>/sources')
def research_sources(research_id):
    """Get sources for a specific research."""
    research = Research.query.get_or_404(research_id)
    sources = Source.query.filter_by(research_id=research_id).order_by(
        desc(Source.relevance_score)
    ).all()
    
    return jsonify({
        'research_id': research_id,
        'sources': [{
            'id': source.id,
            'title': source.title,
            'url': source.url,
            'content_snippet': source.content_snippet,
            'relevance_score': source.relevance_score,
            'domain': source.domain,
            'published_date': source.published_date.isoformat() if source.published_date else None,
            'content_type': source.content_type,
            'language': source.language,
            'credibility_score': source.credibility_score,
            'discovered_via_query': source.discovered_via_query,
            'position_in_results': source.position_in_results
        } for source in sources]
    })


@api_bp.route('/stats/dashboard')
def dashboard_stats():
    """Get statistics for dashboard display."""
    
    # Basic counts
    total_research = Research.query.count()
    completed_research = Research.query.filter_by(status='completed').count()
    in_progress_research = Research.query.filter_by(status='in_progress').count()
    failed_research = Research.query.filter_by(status='failed').count()
    
    # Recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_activity = Research.query.filter(
        Research.started_at >= week_ago
    ).count()
    
    # Language distribution
    language_stats = db.session.query(
        Research.research_language,
        func.count(Research.id)
    ).group_by(Research.research_language).all()
    
    # Daily activity for last 30 days
    month_ago = datetime.utcnow() - timedelta(days=30)
    daily_activity = db.session.query(
        func.date(Research.started_at).label('date'),
        func.count(Research.id).label('count')
    ).filter(
        Research.started_at >= month_ago
    ).group_by(
        func.date(Research.started_at)
    ).order_by('date').all()
    
    return jsonify({
        'totals': {
            'total_research': total_research,
            'completed_research': completed_research,
            'in_progress_research': in_progress_research,
            'failed_research': failed_research,
            'success_rate': round((completed_research / total_research * 100) if total_research > 0 else 0, 1)
        },
        'recent_activity': recent_activity,
        'language_distribution': [
            {'language': lang, 'count': count} for lang, count in language_stats
        ],
        'daily_activity': [
            {'date': date.isoformat() if date else None, 'count': count} 
            for date, count in daily_activity
        ]
    })


@api_bp.errorhandler(404)
def api_not_found(error):
    """API 404 error handler."""
    return jsonify({'error': 'Endpoint not found'}), 404


@api_bp.errorhandler(500)
def api_internal_error(error):
    """API 500 error handler."""
    return jsonify({'error': 'Internal server error'}), 500