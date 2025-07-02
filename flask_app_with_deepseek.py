#!/usr/bin/env python3
"""
Flask app with DeepSeek as primary provider and improved rate limiting.
DeepSeek is ~50-100x cheaper than OpenAI/Anthropic!
"""

import os
import sys
import asyncio
import threading
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
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
        print("\n💡 Get DeepSeek API key (recommended):")
        print("   1. Visit: https://platform.deepseek.com/")
        print("   2. Sign up for free credits")
        print("   3. Generate API key")
        print("   4. Add to .env: DEEPSEEK_API_KEY=your_key_here")
        return False, []
    
    # Check for required Tavily key
    if not os.environ.get('TAVILY_API_KEY'):
        print("❌ Missing TAVILY_API_KEY for web search")
        print("💡 Get Tavily API key:")
        print("   1. Visit: https://tavily.com/")
        print("   2. Sign up for free tier")
        print("   3. Add to .env: TAVILY_API_KEY=your_key_here")
        return False, available_llm
    
    print("✅ Required API keys are set!")
    print(f"📋 Available LLM providers: {', '.join(available_llm).upper()}")
    return True, available_llm

def create_research_app():
    """Create Flask app with DeepSeek primary and smart fallbacks."""
    
    from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
    from flask_cors import CORS
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    CORS(app)
    
    # Simple in-memory storage for demo
    research_storage = {}
    
    # Import improved components
    from improved_rate_limiting import create_improved_llm_client, research_queue
    
    # Determine optimal provider configuration
    has_deepseek = bool(os.environ.get('DEEPSEEK_API_KEY'))
    has_openai = bool(os.environ.get('OPENAI_API_KEY'))
    has_anthropic = bool(os.environ.get('ANTHROPIC_API_KEY'))
    
    # Smart provider selection (OpenAI primary, DeepSeek fallback, Anthropic final)
    final_fallback = None  # Initialize to avoid scope issues
    
    if has_openai:
        primary_provider = "openai"
        # Multi-tier fallback system
        if has_deepseek and has_anthropic:
            fallback_provider = "deepseek"  # First fallback
            final_fallback = "anthropic"    # Final fallback
            cost_status = "🎯 OpenAI → DeepSeek → Anthropic fallback chain"
        elif has_deepseek:
            fallback_provider = "deepseek"
            final_fallback = None
            cost_status = "🎯 OpenAI primary with DeepSeek fallback"
        elif has_anthropic:
            fallback_provider = "anthropic"
            final_fallback = None
            cost_status = "💸 OpenAI primary with Anthropic fallback"
        else:
            fallback_provider = None
            final_fallback = None
            cost_status = "⚠️ OpenAI only (no fallback)"
    elif has_deepseek:
        primary_provider = "deepseek"
        fallback_provider = "anthropic" if has_anthropic else None
        final_fallback = None
        cost_status = "💰 DeepSeek primary (ultra-low cost)"
    elif has_anthropic:
        primary_provider = "anthropic"
        fallback_provider = None
        final_fallback = None
        cost_status = "💸 Anthropic only (premium cost)"
    else:
        raise ValueError("No LLM provider available")
    
    @app.route('/')
    def home():
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>AI Research Assistant - DeepSeek Enhanced</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-success">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">
                <i class="bi bi-search me-2"></i>AI Research Assistant
            </a>
            <span class="navbar-text text-light">
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
                    <div class="card-header bg-success text-white">
                        <h4 class="mb-0">
                            <i class="bi bi-search me-2"></i>Start AI Research
                        </h4>
                        <small>Powered by {{ primary_provider.title() }}{% if fallback_provider %} → {{ fallback_provider.title() }}{% endif %}{% if final_fallback %} → {{ final_fallback.title() }}{% endif %} fallback chain</small>
                    </div>
                    <div class="card-body">
                        <form method="POST" action="/submit_research">
                            <div class="mb-3">
                                <label class="form-label fw-bold">Research Topic</label>
                                <textarea class="form-control form-control-lg" name="topic" rows="3" 
                                    placeholder="Enter your research topic (e.g., 'AI trends in 2025', 'Climate change solutions')" 
                                    required minlength="10"></textarea>
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
                                    <select class="form-select" name="language">
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
                                    <select class="form-select" name="depth">
                                        <option value="basic">Basic (Faster & Cheaper)</option>
                                        <option value="advanced">Advanced (More Thorough)</option>
                                    </select>
                                </div>
                            </div>
                            
                            <div class="d-grid">
                                <button type="submit" class="btn btn-success btn-lg">
                                    <i class="bi bi-play-circle me-2"></i>Start Research
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-4">
                <div class="card shadow-sm">
                    <div class="card-header bg-success text-white">
                        <h6 class="mb-0">
                            <i class="bi bi-cpu me-1"></i>AI Configuration
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
                                <span>Request Queue:</span>
                                <span class="text-success">✓ Smart</span>
                            </div>
                        </div>
                        
                        <hr>
                        
                        <div class="alert alert-info p-2 mb-3">
                            <small>
                                <i class="bi bi-translate me-1"></i>
                                <strong>Translation Features:</strong><br>
                                • Automatic language detection<br>
                                • Multi-language research reports<br>
                                • Cross-language source analysis<br>
                                • Native language presentations
                            </small>
                        </div>
                        
                        {% if primary_provider == 'deepseek' %}
                        <div class="alert alert-success p-2 mb-3">
                            <small>
                                <i class="bi bi-piggy-bank me-1"></i>
                                <strong>DeepSeek Benefits:</strong><br>
                                • ~50-100x cheaper than OpenAI<br>
                                • High-quality outputs<br>
                                • Generous rate limits<br>
                                • Free tier available
                            </small>
                        </div>
                        {% endif %}
                        
                        <div class="small">
                            <div class="d-flex justify-content-between">
                                <span>DeepSeek API:</span>
                                <span class="{{ 'text-success' if has_deepseek else 'text-muted' }}">{{ "✓" if has_deepseek else "○" }}</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>OpenAI API:</span>
                                <span class="{{ 'text-success' if has_openai else 'text-muted' }}">{{ "✓" if has_openai else "○" }}</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>Anthropic API:</span>
                                <span class="{{ 'text-success' if has_anthropic else 'text-muted' }}">{{ "✓" if has_anthropic else "○" }}</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>Tavily API:</span>
                                <span class="text-success">{{ "✓" if tavily_key else "✗" }}</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                {% if recent_research %}
                <div class="card shadow-sm mt-3">
                    <div class="card-header">
                        <h6 class="mb-0">Recent Research</h6>
                    </div>
                    <div class="card-body p-0">
                        {% for research in recent_research %}
                        <div class="list-group-item">
                            <strong>{{ research.topic[:50] }}...</strong><br>
                            <small class="text-muted">{{ research.status }}</small>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
        """, 
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        final_fallback=final_fallback,
        cost_status=cost_status,
        has_deepseek=has_deepseek,
        has_openai=has_openai,
        has_anthropic=has_anthropic,
        tavily_key=bool(os.environ.get('TAVILY_API_KEY')),
        recent_research=list(research_storage.values())[-5:])
    
    @app.route('/submit_research', methods=['POST'])
    def submit_research():
        """Submit research request with DeepSeek optimization."""
        
        topic = request.form.get('topic', '').strip()
        focus_areas = request.form.get('focus_areas', '').strip()
        language = request.form.get('language', 'en')
        depth = request.form.get('depth', 'basic')
        
        if len(topic) < 10:
            flash('Please enter a research topic with at least 10 characters.', 'error')
            return redirect(url_for('home'))
        
        # Create research ID
        research_id = len(research_storage) + 1
        
        # Store research request
        research_storage[research_id] = {
            'id': research_id,
            'topic': topic,
            'focus_areas': focus_areas.split(',') if focus_areas else [],
            'language': language,
            'depth': depth,
            'status': 'queued',
            'started_at': datetime.now(),
            'progress': 0,
            'provider': primary_provider
        }
        
        # Start background research with DeepSeek
        def run_research():
            try:
                # Use the global research queue to limit concurrent requests
                async def research_with_queue():
                    async with research_queue:
                        research_storage[research_id]['status'] = 'in_progress'
                        research_storage[research_id]['progress'] = 20
                        
                        # Import and use enhanced research components
                        from src.tools.web_search import WebSearchTool
                        from src.tools.report_writer import MarkdownWriter
                        from src.agents.multilang_research_agent import MultiLanguageResearchAgent
                        
                        # Initialize enhanced LLM client with multi-tier fallback
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
                        
                        web_search = WebSearchTool(api_key=os.environ.get('TAVILY_API_KEY'))
                        report_writer = MarkdownWriter()
                        
                        research_storage[research_id]['progress'] = 40
                        
                        # Create multilingual research agent with enhanced client
                        agent = MultiLanguageResearchAgent(
                            name="MultiLangWebResearcher",
                            llm_client=llm_client,
                            web_search_tool=web_search,
                            report_writer=report_writer,
                            default_language='en',
                            target_languages=[language] if language != 'en' else ['en'],
                            enable_translation=True
                        )
                        
                        research_storage[research_id]['progress'] = 60
                        
                        # Run multilingual research with improved error handling
                        if language != 'en':
                            # Use multilingual research for non-English languages
                            result = await agent.conduct_multilang_research(
                                topic=topic,
                                focus_areas=focus_areas.split(',') if focus_areas else None,
                                target_languages=[language, 'en'],  # Always include English
                                search_depth=depth
                            )
                        else:
                            # Use standard research for English
                            result = await agent.conduct_research(
                                topic=topic,
                                focus_areas=focus_areas.split(',') if focus_areas else None
                            )
                        
                        # Store results with translation metadata
                        research_storage[research_id].update({
                            'status': 'completed',
                            'progress': 100,
                            'executive_summary': result.get('analysis', ''),
                            'key_findings': [],  
                            'detailed_analysis': result.get('analysis', ''),
                            'total_queries': result.get('total_queries', 0),
                            'total_sources': result.get('total_sources', 0),
                            'report_path': result.get('report_path', ''),
                            'language_metadata': result.get('language_metadata', {}),
                            'translations': result.get('translations', {}),
                            'has_translations': bool(result.get('translations')),
                            'completed_at': datetime.now()
                        })
                
                # Run the async research function
                asyncio.run(research_with_queue())
                
            except Exception as e:
                error_msg = str(e)
                if 'quota' in error_msg.lower() or 'rate limit' in error_msg.lower():
                    status_msg = 'temporarily_unavailable'
                    friendly_error = "Service temporarily unavailable due to high demand. Please try again in a few minutes."
                else:
                    status_msg = 'failed'
                    friendly_error = f"Research failed: {error_msg}"
                
                research_storage[research_id].update({
                    'status': status_msg,
                    'error': friendly_error,
                    'completed_at': datetime.now()
                })
        
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
        """Show research progress with provider information."""
        
        research = research_storage.get(research_id)
        if not research:
            flash('Research not found.', 'error')
            return redirect(url_for('home'))
        
        # Enhanced status messages
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
    <title>Research Progress - DeepSeek Enhanced</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    {% if research.status in ['queued', 'in_progress'] %}
    <meta http-equiv="refresh" content="5">
    {% endif %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-success">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">
                <i class="bi bi-search me-2"></i>AI Research Assistant
            </a>
            <span class="navbar-text text-light">
                <small>{{ cost_status }}</small>
            </span>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-lg-8">
                <div class="card shadow-sm">
                    <div class="card-header bg-success text-white">
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
                                <div class="progress-bar progress-bar-striped progress-bar-animated bg-success" 
                                     style="width: {{ research.progress }}%"></div>
                            </div>
                            <small class="text-muted">Status: {{ status_messages.get(research.status, research.status).title() }}</small>
                        </div>
                        
                        {% if research.status == 'completed' %}
                        <div class="alert alert-success">
                            <h5>✅ Research Completed!</h5>
                            <p><strong>Executive Summary:</strong></p>
                            <p>{{ research.executive_summary }}</p>
                            
                            {% if research.has_translations %}
                            <div class="mt-3">
                                <h6><i class="bi bi-translate me-1"></i>Translation Available</h6>
                                <p class="text-muted">This research includes translations and multilingual analysis.</p>
                                <div class="language-metadata">
                                    {% if research.language_metadata %}
                                    <small>
                                        <strong>Original Language:</strong> {{ research.language_metadata.get('original_language', 'auto-detected') }}<br>
                                        <strong>Research Language:</strong> {{ research.language_metadata.get('research_language', 'en') }}<br>
                                        <strong>Target Languages:</strong> {{ ', '.join(research.language_metadata.get('target_languages', [])) }}
                                    </small>
                                    {% endif %}
                                </div>
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
                                    <strong>Languages:</strong> 
                                    {% if research.has_translations %}
                                        <span class="badge bg-info">{{ research.language_metadata.get('target_languages', [])|length if research.language_metadata else 1 }}</span>
                                    {% else %}
                                        <span class="badge bg-secondary">1</span>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                        {% elif research.status == 'temporarily_unavailable' %}
                        <div class="alert alert-warning">
                            <h5>⏳ Service Temporarily Unavailable</h5>
                            <p>{{ research.error }}</p>
                            <p><strong>What you can try:</strong></p>
                            <ul>
                                <li>Wait a few minutes and submit a new research request</li>
                                <li>Try during off-peak hours</li>
                                <li>Break down complex topics into smaller requests</li>
                            </ul>
                        </div>
                        {% elif research.status == 'failed' %}
                        <div class="alert alert-danger">
                            <h5>❌ Research Failed</h5>
                            <p>{{ research.error }}</p>
                        </div>
                        {% else %}
                        <div class="text-center">
                            <div class="spinner-border text-success" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-2">
                                {% if research.status == 'queued' %}
                                Research queued for {{ primary_provider.title() }} processing...
                                {% else %}
                                Research in progress with {{ primary_provider.title() }}...
                                {% endif %}
                                Page will auto-refresh.
                            </p>
                        </div>
                        {% endif %}
                        
                        <div class="text-center mt-3">
                            <a href="/" class="btn btn-outline-success">
                                <i class="bi bi-house me-1"></i>Back to Home
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
        """, research=research, status_messages=status_messages, 
        primary_provider=primary_provider, cost_status=cost_status)
    
    @app.route('/api/research/<int:research_id>/status')
    def research_status_api(research_id):
        """Get research status as JSON."""
        research = research_storage.get(research_id)
        if not research:
            return jsonify({'error': 'Research not found'}), 404
        
        return jsonify(research)
    
    return app

if __name__ == '__main__':
    print("🚀 AI Research Assistant - Multi-Language with DeepSeek")
    print("=" * 60)
    
    requirements_ok, available_providers = check_requirements()
    if not requirements_ok:
        print("\n❌ Cannot start without required API keys.")
        sys.exit(1)
    
    print("🌐 Starting DeepSeek-enhanced Flask server...")
    print("📌 Access at: http://localhost:5003")
    print("   (or http://172.23.232.50:5003 for WSL)")
    print()
    print("💰 Cost Optimization:")
    if 'deepseek' in available_providers:
        print("   ✅ DeepSeek primary - Ultra-low cost (~$0.14/1M tokens)")
    if 'openai' in available_providers:
        print("   📋 OpenAI available - Standard cost (~$10/1M tokens)")
    if 'anthropic' in available_providers:
        print("   📋 Anthropic available - Premium cost (~$15/1M tokens)")
    print()
    print("✨ Enhanced Features:")
    print("   - 🌍 Multi-language research and translation")
    print("   - 🔄 Smart rate limiting prevents quota exhaustion")
    print("   - 🔀 Automatic API fallback for reliability")
    print("   - ⏳ Request queuing prevents API overload")
    print("   - 💰 Cost-optimized provider selection")
    print("   - 🔤 12 Indo-European languages with auto-detection")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 60)
    
    app = create_research_app()
    app.run(host='0.0.0.0', port=5003, debug=False, use_reloader=False)