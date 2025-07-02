"""
History blueprint for browsing and managing research history.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import desc, func, and_, or_
from datetime import datetime, timedelta

from ..models import Research, db
from ..forms import HistoryFilterForm

history_bp = Blueprint('history', __name__)


@history_bp.route('/')
def index():
    """Research history page with filtering and pagination."""
    form = HistoryFilterForm()
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    language = request.args.get('language', '')
    date_range = request.args.get('date_range', '')
    
    # Build query
    query = Research.query
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Research.topic.contains(search),
                Research.executive_summary.contains(search)
            )
        )
        form.search.data = search
    
    if status:
        query = query.filter(Research.status == status)
        form.status.data = status
    
    if language:
        query = query.filter(Research.research_language == language)
        form.language.data = language
    
    if date_range:
        now = datetime.utcnow()
        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == 'week':
            start_date = now - timedelta(days=7)
        elif date_range == 'month':
            start_date = now - timedelta(days=30)
        elif date_range == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = None
        
        if start_date:
            query = query.filter(Research.started_at >= start_date)
        form.date_range.data = date_range
    
    # Order by most recent
    query = query.order_by(desc(Research.started_at))
    
    # Paginate
    per_page = 20
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    research_list = pagination.items
    
    # Get summary statistics for current filter
    total_count = query.count()
    completed_count = query.filter(Research.status == 'completed').count()
    in_progress_count = query.filter(Research.status == 'in_progress').count()
    failed_count = query.filter(Research.status == 'failed').count()
    
    stats = {
        'total': total_count,
        'completed': completed_count,
        'in_progress': in_progress_count,
        'failed': failed_count
    }
    
    return render_template(
        'history/index.html',
        form=form,
        research_list=research_list,
        pagination=pagination,
        stats=stats
    )


@history_bp.route('/delete/<int:research_id>', methods=['POST'])
def delete(research_id):
    """Delete a research record."""
    research = Research.query.get_or_404(research_id)
    
    # Only allow deletion of completed or failed research
    if research.status == 'in_progress':
        flash('Cannot delete research that is currently in progress.', 'error')
        return redirect(url_for('history.index'))
    
    topic = research.topic
    db.session.delete(research)
    db.session.commit()
    
    flash(f'Research "{topic}" has been deleted.', 'success')
    return redirect(url_for('history.index'))


@history_bp.route('/compare')
def compare():
    """Compare multiple research results."""
    research_ids = request.args.getlist('research_ids', type=int)
    
    if len(research_ids) < 2:
        flash('Please select at least 2 research items to compare.', 'error')
        return redirect(url_for('history.index'))
    
    if len(research_ids) > 5:
        flash('You can compare a maximum of 5 research items at once.', 'error')
        return redirect(url_for('history.index'))
    
    research_list = Research.query.filter(
        Research.id.in_(research_ids),
        Research.status == 'completed'
    ).all()
    
    if len(research_list) != len(research_ids):
        flash('Some selected research items could not be found or are not completed.', 'error')
        return redirect(url_for('history.index'))
    
    return render_template('history/compare.html', research_list=research_list)


@history_bp.route('/export')
def export():
    """Export research history to various formats."""
    format_type = request.args.get('format', 'json')
    
    # Get filtered research based on current query parameters
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    language = request.args.get('language', '')
    date_range = request.args.get('date_range', '')
    
    # Build query (same logic as index)
    query = Research.query
    
    if search:
        query = query.filter(
            or_(
                Research.topic.contains(search),
                Research.executive_summary.contains(search)
            )
        )
    
    if status:
        query = query.filter(Research.status == status)
    
    if language:
        query = query.filter(Research.research_language == language)
    
    if date_range:
        now = datetime.utcnow()
        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == 'week':
            start_date = now - timedelta(days=7)
        elif date_range == 'month':
            start_date = now - timedelta(days=30)
        elif date_range == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = None
        
        if start_date:
            query = query.filter(Research.started_at >= start_date)
    
    research_list = query.order_by(desc(Research.started_at)).all()
    
    if format_type == 'json':
        from flask import jsonify
        return jsonify({
            'research': [research.to_dict() for research in research_list],
            'exported_at': datetime.utcnow().isoformat(),
            'total_count': len(research_list)
        })
    
    elif format_type == 'csv':
        from flask import Response
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Topic', 'Status', 'Started At', 'Completed At', 
            'Processing Time', 'Language', 'Total Queries', 'Total Sources'
        ])
        
        # Write data
        for research in research_list:
            writer.writerow([
                research.id,
                research.topic,
                research.status,
                research.started_at.isoformat() if research.started_at else '',
                research.completed_at.isoformat() if research.completed_at else '',
                research.processing_time or '',
                research.research_language or '',
                research.total_queries or 0,
                research.total_sources or 0
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="research_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            }
        )
    
    else:
        flash('Invalid export format requested.', 'error')
        return redirect(url_for('history.index'))