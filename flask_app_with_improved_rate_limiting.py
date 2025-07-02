#!/usr/bin/env python3
"""
Flask app with improved rate limiting and error handling.
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
    
    required_vars = {
        'OPENAI_API_KEY': 'OpenAI API key for LLM functionality',
        'TAVILY_API_KEY': 'Tavily API key for web search'
    }
    
    missing = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing.append(f"  - {var}: {description}")
    
    if missing:
        print("❌ Missing required environment variables:")
        for item in missing:
            print(item)
        print("\n💡 Set them with:")
        print("   export OPENAI_API_KEY='your-key'")
        print("   export TAVILY_API_KEY='your-key'")
        print("\n   Or create a .env file using .env.template as a guide")
        return False
    
    print("✅ All required environment variables are set!")
    return True

def create_research_app():
    """Create Flask app with improved error handling and rate limiting."""
    
    from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
    from flask_cors import CORS
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    CORS(app)
    
    # Simple in-memory storage for demo
    research_storage = {}
    
    # Import improved components
    from improved_rate_limiting import create_improved_llm_client, research_queue
    
    @app.route('/')
    def home():
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>AI Research Assistant - Enhanced</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">
                <i class="bi bi-search me-2"></i>AI Research Assistant - Enhanced
            </a>
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
                        <small>Enhanced with rate limiting and fallback support</small>
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
                                    <label class="form-label">Language</label>
                                    <select class="form-select" name="language">
                                        <option value="en">English</option>
                                        <option value="sl">Slovenian</option>
                                        <option value="de">German</option>
                                        <option value="fr">French</option>
                                    </select>
                                </div>
                                <div class="col-md-6 mb-3">
                                    <label class="form-label">Search Depth</label>
                                    <select class="form-select" name="depth">
                                        <option value="basic">Basic (Faster)</option>
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
                    <div class="card-header">
                        <h6 class="mb-0">
                            <i class="bi bi-shield-check me-1"></i>Enhanced Features
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="small">
                            <div class="d-flex justify-content-between mb-2">
                                <span>Rate Limiting:</span>
                                <span class="text-success">✓ Active</span>
                            </div>
                            <div class="d-flex justify-content-between mb-2">
                                <span>API Fallback:</span>
                                <span class="text-success">✓ Configured</span>
                            </div>
                            <div class="d-flex justify-content-between mb-2">
                                <span>Request Queue:</span>
                                <span class="text-success">✓ Active</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>Error Recovery:</span>
                                <span class="text-success">✓ Enhanced</span>
                            </div>
                        </div>
                        
                        <hr>
                        
                        <div class="small">
                            <div class="d-flex justify-content-between">
                                <span>OpenAI API:</span>
                                <span class="text-success">{{ "✓" if openai_key else "✗" }}</span>
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
        """, openai_key=bool(os.environ.get('OPENAI_API_KEY')), 
             tavily_key=bool(os.environ.get('TAVILY_API_KEY')),
             recent_research=list(research_storage.values())[-5:])
    
    @app.route('/submit_research', methods=['POST'])
    def submit_research():
        """Submit research request with improved error handling."""
        
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
            'progress': 0
        }
        
        # Start background research with improved error handling
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
                        from src.agents.research_agent import ResearchAgent
                        
                        # Initialize enhanced LLM client with fallback
                        llm_client = create_improved_llm_client(
                            primary_provider="openai",
                            fallback_provider="anthropic" if os.environ.get('ANTHROPIC_API_KEY') else None,
                            openai_api_key=os.environ.get('OPENAI_API_KEY'),
                            anthropic_api_key=os.environ.get('ANTHROPIC_API_KEY'),
                            openai_model="gpt-4"
                        )
                        
                        web_search = WebSearchTool(api_key=os.environ.get('TAVILY_API_KEY'))
                        report_writer = MarkdownWriter()
                        
                        research_storage[research_id]['progress'] = 40
                        
                        # Create research agent with enhanced client
                        agent = ResearchAgent(
                            name="WebResearcher",
                            llm_client=llm_client,
                            web_search_tool=web_search,
                            report_writer=report_writer
                        )
                        
                        research_storage[research_id]['progress'] = 60
                        
                        # Run research with improved error handling
                        result = await agent.conduct_research(
                            topic=topic,
                            focus_areas=focus_areas.split(',') if focus_areas else None
                        )
                        
                        # Store results
                        research_storage[research_id].update({
                            'status': 'completed',
                            'progress': 100,
                            'executive_summary': result.get('analysis', ''),
                            'key_findings': [],  
                            'detailed_analysis': result.get('analysis', ''),
                            'total_queries': result.get('total_queries', 0),
                            'total_sources': result.get('total_sources', 0),
                            'report_path': result.get('report_path', ''),
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
        
        flash(f'Research "{topic}" has been queued! Enhanced with rate limiting and fallback support.', 'success')
        return redirect(url_for('research_progress', research_id=research_id))
    
    @app.route('/research/<int:research_id>')
    def research_progress(research_id):
        """Show research progress with enhanced status messages."""
        
        research = research_storage.get(research_id)
        if not research:
            flash('Research not found.', 'error')
            return redirect(url_for('home'))
        
        # Enhanced status messages
        status_messages = {
            'queued': 'Queued - Waiting for available slot',
            'in_progress': 'In Progress - Enhanced with rate limiting',
            'completed': 'Completed Successfully',
            'failed': 'Failed - Please try again',
            'temporarily_unavailable': 'Temporarily Unavailable - High API usage'
        }
        
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Research Progress - Enhanced</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    {% if research.status in ['queued', 'in_progress'] %}
    <meta http-equiv="refresh" content="5">
    {% endif %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">
                <i class="bi bi-search me-2"></i>AI Research Assistant - Enhanced
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
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <div class="d-flex justify-content-between">
                                <span class="fw-bold">Progress</span>
                                <span>{{ research.progress }}%</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                     style="width: {{ research.progress }}%"></div>
                            </div>
                            <small class="text-muted">Status: {{ status_messages.get(research.status, research.status).title() }}</small>
                        </div>
                        
                        {% if research.status == 'completed' %}
                        <div class="alert alert-success">
                            <h5>✅ Research Completed!</h5>
                            <p><strong>Executive Summary:</strong></p>
                            <p>{{ research.executive_summary }}</p>
                            
                            <div class="row mt-3">
                                <div class="col-6">
                                    <strong>Queries:</strong> {{ research.total_queries }}
                                </div>
                                <div class="col-6">
                                    <strong>Sources:</strong> {{ research.total_sources }}
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
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-2">
                                {% if research.status == 'queued' %}
                                Research queued... Waiting for available processing slot.
                                {% else %}
                                Research in progress with enhanced rate limiting...
                                {% endif %}
                                Page will auto-refresh.
                            </p>
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
</body>
</html>
        """, research=research, status_messages=status_messages)
    
    @app.route('/api/research/<int:research_id>/status')
    def research_status_api(research_id):
        """Get research status as JSON."""
        research = research_storage.get(research_id)
        if not research:
            return jsonify({'error': 'Research not found'}), 404
        
        return jsonify(research)
    
    return app

if __name__ == '__main__':
    print("🚀 AI Research Assistant - Enhanced with Rate Limiting")
    print("=" * 60)
    
    if not check_requirements():
        print("\n❌ Cannot start without required API keys.")
        sys.exit(1)
    
    print("🌐 Starting enhanced Flask server...")
    print("📌 Access at: http://localhost:5003")
    print("   (or http://172.23.232.50:5003 for WSL)")
    print()
    print("✨ Enhanced Features:")
    print("   - Smart rate limiting to prevent quota exhaustion")
    print("   - Automatic API fallback (OpenAI ↔ Anthropic)")
    print("   - Request queuing to prevent overwhelming APIs")
    print("   - Graceful error handling and user-friendly messages")
    print("   - Exponential backoff for retry logic")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 60)
    
    app = create_research_app()
    app.run(host='0.0.0.0', port=5003, debug=False, use_reloader=False)