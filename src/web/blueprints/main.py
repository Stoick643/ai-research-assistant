"""
Main blueprint for home page and core functionality.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from sqlalchemy import desc
from datetime import datetime, timedelta

from ..models import Research, db
from ..forms import ResearchForm

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Home page with research form and recent research."""
    form = ResearchForm()
    
    # Get recent research (last 10 completed)
    recent_research = Research.query.filter_by(status='completed').order_by(
        desc(Research.completed_at)
    ).limit(10).all()
    
    return render_template('index.html', form=form, recent_research=recent_research)


@main_bp.route('/about')
def about():
    """About page with information about the research assistant."""
    return render_template('about.html')


@main_bp.route('/help')
def help():
    """Help page with usage instructions."""
    return render_template('help.html')


@main_bp.route('/status')
def status():
    """System status page."""
    
    # Get system statistics
    total_research = Research.query.count()
    completed_research = Research.query.filter_by(status='completed').count()
    in_progress_research = Research.query.filter_by(status='in_progress').count()
    failed_research = Research.query.filter_by(status='failed').count()
    
    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_activity = Research.query.filter(
        Research.started_at >= yesterday
    ).count()
    
    stats = {
        'total_research': total_research,
        'completed_research': completed_research,
        'in_progress_research': in_progress_research,
        'failed_research': failed_research,
        'recent_activity': recent_activity,
        'success_rate': round((completed_research / total_research * 100) if total_research > 0 else 0, 1)
    }
    
    return render_template('status.html', stats=stats)