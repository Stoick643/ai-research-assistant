#!/usr/bin/env python3
"""
Production Flask app for AI Research Assistant with multi-language support.
Optimized for Render deployment.
"""

import os
import sys
import asyncio
import threading
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def check_requirements():
    """Check if required API keys are set."""
    
    # Check for at least one LLM provider
    llm_providers = {
        'DEEPSEEK_API_KEY': 'DeepSeek API key (recommended - very affordable)',
        'OPENAI_API_KEY': 'OpenAI API key (fallback)',
        'ANTHROPIC_API_KEY': 'Anthropic API key (fallback)'
    }
    
    available_llm = []
    for var, description in llm_providers.items():
        if os.environ.get(var):
            available_llm.append(var.replace('_API_KEY', '').lower())
    
    if not available_llm:
        print("❌ No LLM API keys found. You need at least one:")
        for var, description in llm_providers.items():
            print(f"  - {var}: {description}")
        return False, []
    
    # Check for required Tavily key
    if not os.environ.get('TAVILY_API_KEY'):
        print("❌ Missing TAVILY_API_KEY for web search")
        return False, available_llm
    
    print("✅ Required API keys are set!")
    print(f"📋 Available LLM providers: {', '.join(available_llm).upper()}")
    return True, available_llm

def create_production_app():
    """Create production-optimized Flask app."""
    
    from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
    from flask_cors import CORS
    
    app = Flask(__name__)
    
    # Production configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32).hex())
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Enable CORS for production
    CORS(app, origins=["https://*.onrender.com", "https://localhost:*"])
    
    # In-memory progress tracking (transient UI state only)
    # All persistent data lives in the database
    progress_tracker = {}
    
    # Initialize database
    from src.database.sqlite_writer import SQLiteWriter as DbWriter
    db = DbWriter()
    
    # Import improved components
    from src.utils.rate_limiting import create_improved_llm_client, research_queue
    
    # Determine provider configuration
    has_deepseek = bool(os.environ.get('DEEPSEEK_API_KEY'))
    has_openai = bool(os.environ.get('OPENAI_API_KEY'))
    has_anthropic = bool(os.environ.get('ANTHROPIC_API_KEY'))
    
    # Smart provider selection (OpenAI primary, DeepSeek fallback, Anthropic final)
    final_fallback = None
    
    if has_openai:
        primary_provider = "openai"
        if has_deepseek and has_anthropic:
            fallback_provider = "deepseek"
            final_fallback = "anthropic"
            cost_status = "🎯 OpenAI → DeepSeek → Anthropic fallback chain"
        elif has_deepseek:
            fallback_provider = "deepseek"
            cost_status = "🎯 OpenAI primary with DeepSeek fallback"
        elif has_anthropic:
            fallback_provider = "anthropic"
            cost_status = "💸 OpenAI primary with Anthropic fallback"
        else:
            fallback_provider = None
            cost_status = "⚠️ OpenAI only (no fallback)"
    elif has_deepseek:
        primary_provider = "deepseek"
        fallback_provider = "anthropic" if has_anthropic else None
        cost_status = "💰 DeepSeek primary (ultra-low cost)"
    elif has_anthropic:
        primary_provider = "anthropic"
        fallback_provider = None
        cost_status = "💸 Anthropic only (premium cost)"
    else:
        raise ValueError("No LLM provider available")
    
    @app.route('/health')
    def health_check():
        """Health check endpoint for Render."""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'providers': {
                'primary': primary_provider,
                'fallback': fallback_provider,
                'final_fallback': final_fallback
            }
        })
    
    @app.route('/')
    def home():
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>AI Research Assistant - Multi-Language</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">
                <i class="bi bi-search me-2"></i>AI Research Assistant
            </a>
            <span class="navbar-text text-light d-none d-md-block">
                <small>{{ cost_status }}</small>
            </span>
        </div>
    </nav>
    
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="row">
            <div class="col-lg-8">
                <div class="card shadow-sm">
                    <div class="card-header bg-primary text-white">
                        <h4 class="mb-0">
                            <i class="bi bi-search me-2"></i>Start AI Research
                        </h4>
                        <small>Multi-language research with intelligent fallback system</small>
                    </div>
                    <div class="card-body">
                        <form method="POST" action="/submit_research" class="needs-validation" novalidate>
                            <div class="mb-3">
                                <label class="form-label fw-bold">Research Topic</label>
                                <textarea class="form-control form-control-lg" name="topic" rows="3" 
                                    placeholder="Enter your research topic (e.g., 'AI trends in 2025', 'Climate change solutions')" 
                                    required minlength="10"></textarea>
                                <div class="invalid-feedback">
                                    Please enter a research topic with at least 10 characters.
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Focus Areas (Optional)</label>
                                <input type="text" class="form-control" name="focus_areas" 
                                    placeholder="Specific areas to focus on (comma-separated)">
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6 mb-3">
                                    <label class="form-label">
                                        <i class="bi bi-translate me-1"></i>Research Language
                                    </label>
                                    <select class="form-select" name="language" required>
                                        <option value="en">English</option>
                                        <option value="sl">Slovenian (slovenski)</option>
                                        <option value="de">German (Deutsch)</option>
                                        <option value="fr">French (Français)</option>
                                        <option value="es">Spanish (Español)</option>
                                        <option value="it">Italian (Italiano)</option>
                                        <option value="pt">Portuguese (Português)</option>
                                        <option value="ru">Russian (Русский)</option>
                                        <option value="nl">Dutch (Nederlands)</option>
                                        <option value="sr">Serbian (Српски)</option>
                                        <option value="mk">Macedonian (Македонски)</option>
                                        <option value="hr">Croatian (Hrvatski)</option>
                                    </select>
                                    <small class="text-muted">Research will be conducted in English and translated to selected language</small>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <label class="form-label">Search Depth</label>
                                    <select class="form-select" name="depth" required>
                                        <option value="basic">Basic (Faster & Cheaper)</option>
                                        <option value="advanced">Advanced (More Thorough)</option>
                                    </select>
                                </div>
                            </div>
                            
                            <div class="d-grid">
                                <button type="submit" class="btn btn-primary btn-lg">
                                    <i class="bi bi-play-circle me-2"></i>Start Research
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-4">
                <div class="card shadow-sm">
                    <div class="card-header bg-primary text-white">
                        <h6 class="mb-0">
                            <i class="bi bi-cpu me-1"></i>System Status
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="small">
                            <div class="d-flex justify-content-between mb-2">
                                <span>Primary LLM:</span>
                                <span class="text-success fw-bold">{{ primary_provider.title() }}</span>
                            </div>
                            {% if fallback_provider %}
                            <div class="d-flex justify-content-between mb-2">
                                <span>1st Fallback:</span>
                                <span class="text-info">{{ fallback_provider.title() }}</span>
                            </div>
                            {% endif %}
                            {% if final_fallback %}
                            <div class="d-flex justify-content-between mb-2">
                                <span>2nd Fallback:</span>
                                <span class="text-warning">{{ final_fallback.title() }}</span>
                            </div>
                            {% endif %}
                            <div class="d-flex justify-content-between mb-2">
                                <span>Rate Limiting:</span>
                                <span class="text-success">✓ Active</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>Translation:</span>
                                <span class="text-success">✓ 12 Languages</span>
                            </div>
                        </div>
                        
                        <hr>
                        
                        <div class="alert alert-info p-2 mb-3">
                            <small>
                                <i class="bi bi-translate me-1"></i>
                                <strong>Translation Features:</strong><br>
                                • 12 Indo-European languages<br>
                                • Automatic language detection<br>
                                • Bilingual report generation<br>
                                • Cross-language analysis
                            </small>
                        </div>
                        
                        <div class="small">
                            <div class="d-flex justify-content-between">
                                <span>System Health:</span>
                                <span class="text-success">✓ Online</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Form validation
        (function() {
            'use strict';
            window.addEventListener('load', function() {
                var forms = document.getElementsByClassName('needs-validation');
                var validation = Array.prototype.filter.call(forms, function(form) {
                    form.addEventListener('submit', function(event) {
                        if (form.checkValidity() === false) {
                            event.preventDefault();
                            event.stopPropagation();
                        }
                        form.classList.add('was-validated');
                    }, false);
                });
            }, false);
        })();
    </script>
</body>
</html>
        """, 
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        final_fallback=final_fallback,
        cost_status=cost_status)
    
    @app.route('/submit_research', methods=['POST'])
    def submit_research():
        """Submit research request with production error handling."""
        
        topic = request.form.get('topic', '').strip()
        focus_areas = request.form.get('focus_areas', '').strip()
        language = request.form.get('language', 'en')
        depth = request.form.get('depth', 'basic')
        
        if len(topic) < 10:
            flash('Please enter a research topic with at least 10 characters.', 'error')
            return redirect(url_for('home'))
        
        # Create research record in database
        from src.database.models import Research
        with db.db_manager.get_session() as session:
            research = Research(
                topic=topic,
                focus_areas=focus_areas.split(',') if focus_areas else [],
                agent_name="MultiLangWebResearcher",
                status='queued',
                research_language=language,
                research_metadata={'depth': depth, 'provider': primary_provider},
            )
            session.add(research)
            session.flush()
            research_id = research.id
        
        # Track progress in memory (transient)
        progress_tracker[research_id] = {'progress': 0}
        
        # Start background research
        def run_research():
            try:
                async def research_with_queue():
                    async with research_queue:
                        db.update_research_status(research_id, 'in_progress')
                        progress_tracker[research_id]['progress'] = 20
                        
                        # Import research components
                        from src.tools.web_search import WebSearchTool
                        from src.tools.search_cache import SearchCache
                        from src.tools.report_writer import MarkdownWriter
                        from src.agents.multilang_research_agent import MultiLanguageResearchAgent
                        
                        # Initialize enhanced LLM client
                        llm_client = create_improved_llm_client(
                            primary_provider=primary_provider,
                            fallback_provider=fallback_provider,
                            final_fallback_provider=final_fallback,
                            deepseek_api_key=os.environ.get('DEEPSEEK_API_KEY'),
                            openai_api_key=os.environ.get('OPENAI_API_KEY'),
                            anthropic_api_key=os.environ.get('ANTHROPIC_API_KEY'),
                            deepseek_model="deepseek-chat",
                            openai_model="gpt-4"
                        )
                        
                        search_cache = SearchCache()
                        web_search = WebSearchTool(api_key=os.environ.get('TAVILY_API_KEY'), search_cache=search_cache)
                        report_writer = MarkdownWriter()
                        
                        progress_tracker[research_id]['progress'] = 40
                        
                        # Create multilingual research agent
                        agent = MultiLanguageResearchAgent(
                            name="MultiLangWebResearcher",
                            llm_client=llm_client,
                            web_search_tool=web_search,
                            report_writer=report_writer,
                            default_language='en',
                            target_languages=[language] if language != 'en' else ['en'],
                            enable_translation=True
                        )
                        
                        progress_tracker[research_id]['progress'] = 60
                        
                        # Run research
                        if language != 'en':
                            result = await agent.conduct_multilang_research(
                                topic=topic,
                                focus_areas=focus_areas.split(',') if focus_areas else None,
                                target_languages=[language, 'en'],
                                search_depth=depth
                            )
                        else:
                            result = await agent.conduct_research(
                                topic=topic,
                                focus_areas=focus_areas.split(',') if focus_areas else None
                            )
                        
                        # Update database with results
                        with db.db_manager.get_session() as session:
                            from src.database.models import Research as ResearchModel
                            rec = session.query(ResearchModel).get(research_id)
                            if rec:
                                rec.status = 'completed'
                                rec.completed_at = datetime.utcnow()
                                rec.processing_time = (datetime.utcnow() - rec.started_at).total_seconds()
                                rec.executive_summary = result.get('analysis', '')
                                rec.detailed_analysis = result.get('analysis', '')
                                rec.report_content = result.get('report_content', '')
                                rec.total_queries = result.get('total_queries', 0)
                                rec.total_sources = result.get('total_sources', 0)
                                rec.report_path = result.get('report_path', '')
                                rec.research_metadata = {
                                    'depth': depth,
                                    'provider': primary_provider,
                                    'language_metadata': result.get('language_metadata', {}),
                                    'translations': result.get('translations', {}),
                                }
                                rec.translation_enabled = bool(result.get('translations'))
                        
                        progress_tracker[research_id]['progress'] = 100
                
                asyncio.run(research_with_queue())
                
            except Exception as e:
                error_msg = str(e)
                if 'quota' in error_msg.lower() or 'rate limit' in error_msg.lower():
                    status_msg = 'temporarily_unavailable'
                    friendly_error = "Service temporarily unavailable due to high demand. Please try again in a few minutes."
                else:
                    status_msg = 'failed'
                    friendly_error = f"Research failed: {error_msg}"
                
                db.update_research_status(research_id, status_msg, friendly_error)
                progress_tracker[research_id]['progress'] = 0
        
        # Start research in background thread
        thread = threading.Thread(target=run_research)
        thread.daemon = True
        thread.start()
        
        provider_msg = f"using {primary_provider.title()}"
        if fallback_provider and final_fallback:
            provider_msg += f" → {fallback_provider.title()} → {final_fallback.title()} fallback chain"
        elif fallback_provider:
            provider_msg += f" → {fallback_provider.title()} fallback"
        
        flash(f'Research "{topic}" has been queued! {provider_msg}', 'success')
        return redirect(url_for('research_progress', research_id=research_id))
    
    @app.route('/research/<int:research_id>')
    def research_progress(research_id):
        """Show research progress."""
        
        research = db.get_research_by_id(research_id)
        if not research:
            flash('Research not found.', 'error')
            return redirect(url_for('home'))
        
        # Merge transient progress info
        progress_info = progress_tracker.get(research_id, {})
        research['progress'] = progress_info.get('progress', 100 if research['status'] == 'completed' else 0)
        metadata = research.get('research_metadata') or {}
        research['provider'] = metadata.get('provider', primary_provider)
        lang = research.get('research_language', 'en')
        research['language'] = lang
        research['error'] = research.get('error_message', '')
        
        # Use translated summary if available for non-English research
        research['has_translations'] = False
        if lang != 'en' and research['status'] == 'completed':
            translations = metadata.get('translations', {})
            lang_data = translations.get(lang, {})
            translated_summary = lang_data.get('executive_summary', {})
            translated_text = translated_summary.get('text', '')
            if translated_text:
                research['executive_summary'] = translated_text
                research['has_translations'] = True
        
        status_messages = {
            'queued': f'Queued - Waiting for {primary_provider.title()} processing slot',
            'in_progress': f'In Progress - Powered by {primary_provider.title()}',
            'completed': 'Completed Successfully',
            'failed': 'Failed - Please try again',
            'temporarily_unavailable': 'Temporarily Unavailable - High API usage'
        }
        
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Research Progress</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {% if research.status in ['queued', 'in_progress'] %}
    <meta http-equiv="refresh" content="5">
    {% endif %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">
                <i class="bi bi-search me-2"></i>AI Research Assistant
            </a>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-lg-8">
                <div class="card shadow-sm">
                    <div class="card-header bg-primary text-white">
                        <h4 class="mb-0">
                            <i class="bi bi-hourglass-split me-2"></i>{{ research.topic }}
                        </h4>
                        <small>Provider: {{ research.provider.title() if research.provider else primary_provider.title() }}</small>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <div class="d-flex justify-content-between">
                                <span class="fw-bold">Progress</span>
                                <span>{{ research.progress }}%</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar {% if research.status in ['queued', 'in_progress'] %}progress-bar-striped progress-bar-animated{% endif %} bg-{{ 'success' if research.status == 'completed' else 'danger' if research.status == 'failed' else 'primary' }}" 
                                     style="width: {{ research.progress }}%"></div>
                            </div>
                            <small class="text-muted">Status: {{ status_messages.get(research.status, research.status).title() }}</small>
                        </div>
                        
                        {% if research.status == 'completed' %}
                        <div class="alert alert-success">
                            <h5>✅ Research Completed!</h5>
                            <p><strong>Executive Summary:</strong></p>
                            <div id="research-content"></div>
                            <script id="raw-content" type="application/json">{{ research.executive_summary | tojson }}</script>
                            
                            {% if research.has_translations %}
                            <div class="mt-3">
                                <h6><i class="bi bi-translate me-1"></i>Translation Available</h6>
                                <p class="text-muted">This research includes translations and multilingual analysis.</p>
                            </div>
                            {% endif %}
                            
                            <div class="row mt-3">
                                <div class="col-3">
                                    <strong>Queries:</strong> {{ research.total_queries }}
                                </div>
                                <div class="col-3">
                                    <strong>Sources:</strong> {{ research.total_sources }}
                                </div>
                                <div class="col-3">
                                    <strong>Provider:</strong> {{ research.provider.title() if research.provider else primary_provider.title() }}
                                </div>
                                <div class="col-3">
                                    <strong>Language:</strong> {{ research.language.upper() }}
                                </div>
                            </div>
                        </div>
                        {% elif research.status == 'temporarily_unavailable' %}
                        <div class="alert alert-warning">
                            <h5>⏳ Service Temporarily Unavailable</h5>
                            <p>{{ research.error }}</p>
                        </div>
                        {% elif research.status == 'failed' %}
                        <div class="alert alert-danger">
                            <h5>❌ Research Failed</h5>
                            <p>{{ research.error }}</p>
                        </div>
                        {% else %}
                        <div class="text-center">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-2">Research in progress... Page will auto-refresh.</p>
                        </div>
                        {% endif %}
                        
                        <div class="text-center mt-3">
                            <a href="/" class="btn btn-outline-primary">
                                <i class="bi bi-house me-1"></i>Back to Home
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>
        // Render markdown content if present
        var rawEl = document.getElementById('raw-content');
        var contentEl = document.getElementById('research-content');
        if (rawEl && contentEl) {
            var raw = JSON.parse(rawEl.textContent);
            contentEl.innerHTML = marked.parse(raw);
        }
    </script>
</body>
</html>
        """, research=research, status_messages=status_messages, 
        primary_provider=primary_provider)
    
    @app.route('/api/research/<int:research_id>/status')
    def research_status_api(research_id):
        """Get research status as JSON."""
        research = db.get_research_by_id(research_id)
        if not research:
            return jsonify({'error': 'Research not found'}), 404
        
        # Merge transient progress
        progress_info = progress_tracker.get(research_id, {})
        research['progress'] = progress_info.get('progress', 100 if research['status'] == 'completed' else 0)
        
        return jsonify(research)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

# Create the app instance for Gunicorn
app = create_production_app()

if __name__ == '__main__':
    print("🚀 AI Research Assistant - Production Mode")
    print("=" * 50)
    
    requirements_ok, available_providers = check_requirements()
    if not requirements_ok:
        print("\n❌ Cannot start without required API keys.")
        sys.exit(1)
    
    # Development server
    print("🌐 Starting development server...")
    print("📌 For production, use: gunicorn app:app")
    
    port = int(os.environ.get('PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=False)