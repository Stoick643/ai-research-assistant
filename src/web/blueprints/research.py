"""
Research blueprint for handling research requests and results.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime
import json

from ..models import Research, db
from ..forms import ResearchForm
# from ..tasks import conduct_research_task  # Disabled for testing
from ..tasks_simple import simple_research_task

research_bp = Blueprint('research', __name__)


@research_bp.route('/submit', methods=['POST'])
def submit():
    """Submit new research request."""
    form = ResearchForm()
    
    if form.validate_on_submit():
        # Create research record
        research = Research(
            topic=form.topic.data.strip(),
            focus_areas=form.focus_areas.data.split(',') if form.focus_areas.data else None,
            agent_name='WebResearchAgent',
            started_at=datetime.utcnow(),
            status='in_progress',
            original_language=form.source_language.data if form.source_language.data != 'auto' else None,
            research_language='en',  # Always research in English for now
            translation_enabled=form.enable_translation.data,
            translated_languages=form.target_languages.data if form.enable_translation.data else ['en'],
            research_metadata={
                'max_queries': form.max_queries.data,
                'search_depth': form.search_depth.data,
                'submitted_via': 'web_interface'
            }
        )
        
        db.session.add(research)
        db.session.commit()
        
        # Start background research task
        task_data = {
            'topic': research.topic,
            'focus_areas': research.focus_areas,
            'source_language': research.original_language,
            'target_languages': research.translated_languages,
            'max_queries': research.research_metadata['max_queries'],
            'search_depth': research.research_metadata['search_depth']
        }
        
        # Start Celery task (simplified for testing)
        simple_research_task.delay(research.id, task_data)
        
        flash(f'Research "{research.topic}" has been started!', 'success')
        return redirect(url_for('research.view', research_id=research.id))
    
    # If form validation failed, return to home with errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('main.index'))


@research_bp.route('/<int:research_id>')
def view(research_id):
    """View research results."""
    research = Research.query.get_or_404(research_id)
    
    # Get related data
    queries = research.queries
    sources = research.sources
    translations = research.translations
    
    return render_template(
        'research/view.html',
        research=research,
        queries=queries,
        sources=sources,
        translations=translations
    )


@research_bp.route('/<int:research_id>/progress')
def progress(research_id):
    """Show research progress page with real-time updates."""
    research = Research.query.get_or_404(research_id)
    
    if research.status == 'completed':
        return redirect(url_for('research.view', research_id=research_id))
    
    return render_template('research/progress.html', research=research)


@research_bp.route('/<int:research_id>/download')
def download(research_id):
    """Download research report."""
    research = Research.query.get_or_404(research_id)
    
    if research.status != 'completed' or not research.report_content:
        flash('Research report is not available for download.', 'error')
        return redirect(url_for('research.view', research_id=research_id))
    
    from flask import Response
    
    # Create markdown file response
    filename = f"research_report_{research.id}_{research.topic[:50].replace(' ', '_')}.md"
    
    return Response(
        research.report_content,
        mimetype='text/markdown',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@research_bp.route('/<int:research_id>/translation/<language>')
def download_translation(research_id, language):
    """Download translated research report."""
    research = Research.query.get_or_404(research_id)
    translation = next(
        (t for t in research.translations if t.target_language == language), 
        None
    )
    
    if not translation or not translation.translated_analysis:
        flash(f'Translation for {language} is not available.', 'error')
        return redirect(url_for('research.view', research_id=research_id))
    
    from flask import Response
    
    # Create translated markdown content
    content = f"# {research.topic}\n\n"
    content += f"**Language:** {language}\n\n"
    
    if translation.translated_summary:
        content += f"## Summary\n\n{translation.translated_summary}\n\n"
    
    if translation.translated_analysis:
        content += f"## Analysis\n\n{translation.translated_analysis}\n\n"
    
    filename = f"research_report_{research.id}_{language}_{research.topic[:50].replace(' ', '_')}.md"
    
    return Response(
        content,
        mimetype='text/markdown',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )