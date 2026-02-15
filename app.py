#!/usr/bin/env python3
"""
Production Flask app for AI Research Assistant with multi-language support.
Thin HTTP layer — all business logic lives in ResearchService.
"""

import os
import sys
import asyncio
import threading
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def check_requirements():
    """Check if required API keys are set."""
    llm_providers = {
        'DEEPSEEK_API_KEY': 'DeepSeek API key (recommended - very affordable)',
        'OPENAI_API_KEY': 'OpenAI API key (fallback)',
        'ANTHROPIC_API_KEY': 'Anthropic API key (fallback)',
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
    
    if not os.environ.get('TAVILY_API_KEY'):
        print("❌ Missing TAVILY_API_KEY for web search")
        return False, available_llm
    
    print("✅ Required API keys are set!")
    print(f"📋 Available LLM providers: {', '.join(available_llm).upper()}")
    return True, available_llm


def create_production_app():
    """Create production-optimized Flask app."""
    
    from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
    from flask_cors import CORS
    from src.services.research_service import ResearchService
    
    app = Flask(__name__)
    
    # Production configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32).hex())
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    CORS(app, origins=["https://*.onrender.com", "https://localhost:*"])
    
    # Initialize service layer
    svc = ResearchService()
    
    # Server-level provider config (for display when no user keys)
    server_keys = ResearchService.resolve_keys()
    server_primary, server_fallback, server_final = ResearchService.resolve_providers(server_keys)
    
    def _cost_status(pri, fb, ffb):
        if not pri:
            return "⚠️ No provider"
        if pri == "openai":
            if fb and ffb:
                return f"🎯 OpenAI → {fb.title()} → {ffb.title()} fallback chain"
            elif fb:
                return f"🎯 OpenAI primary with {fb.title()} fallback"
            return "⚠️ OpenAI only (no fallback)"
        elif pri == "deepseek":
            return "💰 DeepSeek primary (ultra-low cost)"
        elif pri == "anthropic":
            return "💸 Anthropic only (premium cost)"
        return f"⚠️ {pri.title()} only"
    
    server_cost_status = _cost_status(server_primary, server_fallback, server_final)
    
    # ── BYOK helpers ──────────────────────────────────────────────────
    
    def _get_user_keys():
        return {
            'openai': session.get('openai_api_key'),
            'deepseek': session.get('deepseek_api_key'),
            'anthropic': session.get('anthropic_api_key'),
            'tavily': session.get('tavily_api_key'),
        }
    
    def _effective_config():
        """Return resolved keys + providers for current request."""
        user = _get_user_keys()
        keys = ResearchService.resolve_keys(user)
        pri, fb, ffb = ResearchService.resolve_providers(keys)
        return keys, pri, fb, ffb, user
    
    # ── Routes ─────────────────────────────────────────────────────────
    
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'providers': {
                'primary': server_primary,
                'fallback': server_fallback,
                'final_fallback': server_final,
            }
        })
    
    @app.route('/')
    def home():
        keys, eff_pri, eff_fb, eff_ffb, user = _effective_config()
        any_user = any(v for v in user.values())
        
        return render_template('home.html',
            primary_provider=eff_pri or server_primary,
            fallback_provider=eff_fb or server_fallback,
            final_fallback=eff_ffb or server_final,
            cost_status="🔑 Using your API keys" if any_user else server_cost_status,
            key_sources={
                'primary': ResearchService.key_source_label(eff_pri or server_primary or '', user),
                'tavily': ResearchService.key_source_label('tavily', user),
            })
    
    @app.route('/history')
    def history():
        researches = svc.get_history(limit=100)
        return render_template('history.html', researches=researches)
    
    @app.route('/settings')
    def settings():
        user_keys = _get_user_keys()
        has_server = {
            'tavily': bool(os.environ.get('TAVILY_API_KEY')),
            'openai': bool(os.environ.get('OPENAI_API_KEY')),
            'deepseek': bool(os.environ.get('DEEPSEEK_API_KEY')),
            'anthropic': bool(os.environ.get('ANTHROPIC_API_KEY')),
        }
        return render_template('settings.html', user_keys=user_keys, has_server=has_server)
    
    @app.route('/settings/save', methods=['POST'])
    def settings_save():
        providers = ['tavily', 'openai', 'deepseek', 'anthropic']
        saved = []
        for p in providers:
            key = request.form.get(f'{p}_api_key', '').strip()
            if key:
                session[f'{p}_api_key'] = key
                saved.append(p.title())
        
        if saved:
            flash(f'🔑 Saved keys for: {", ".join(saved)}', 'success')
        else:
            flash('No keys entered. Using server defaults.', 'info')
        return redirect(url_for('settings'))
    
    @app.route('/settings/clear')
    def settings_clear():
        for p in ['tavily', 'openai', 'deepseek', 'anthropic']:
            session.pop(f'{p}_api_key', None)
        flash('🗑️ All your API keys have been cleared. Using server defaults.', 'info')
        return redirect(url_for('settings'))
    
    @app.route('/api/settings/test-key', methods=['POST'])
    def test_api_key():
        data = request.get_json()
        provider = data.get('provider', '')
        api_key = data.get('api_key', '').strip()
        
        if not api_key:
            return jsonify({'success': False, 'message': 'No API key provided'})
        
        try:
            if provider == 'tavily':
                from tavily import TavilyClient
                client = TavilyClient(api_key=api_key)
                client.search("test", max_results=1)
                return jsonify({'success': True, 'message': 'Tavily key is valid ✓'})
            elif provider == 'openai':
                import openai
                client = openai.OpenAI(api_key=api_key)
                models = client.models.list()
                return jsonify({'success': True, 'message': f'OpenAI key is valid ✓ ({len(models.data)} models available)'})
            elif provider == 'deepseek':
                import openai
                client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
                models = client.models.list()
                return jsonify({'success': True, 'message': f'DeepSeek key is valid ✓ ({len(models.data)} models available)'})
            elif provider == 'anthropic':
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                client.messages.count_tokens(
                    model="claude-3-sonnet-20240229",
                    messages=[{"role": "user", "content": "hi"}]
                )
                return jsonify({'success': True, 'message': 'Anthropic key is valid ✓'})
            else:
                return jsonify({'success': False, 'message': f'Unknown provider: {provider}'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/submit_research', methods=['POST'])
    def submit_research():
        topic = request.form.get('topic', '').strip()
        focus_areas = request.form.get('focus_areas', '').strip()
        language = request.form.get('language', 'en')
        depth = request.form.get('depth', 'basic')
        
        if len(topic) < 10:
            flash('Please enter a research topic with at least 10 characters.', 'error')
            return redirect(url_for('home'))
        
        # Resolve keys from session (must capture before background thread)
        resolved, eff_primary, eff_fallback, eff_final, user = _effective_config()
        
        if not eff_primary:
            flash('❌ No LLM provider available. Please add at least one API key in Settings.', 'error')
            return redirect(url_for('settings'))
        if not resolved['tavily_api_key']:
            flash('❌ No Tavily API key available. Please add one in Settings.', 'error')
            return redirect(url_for('settings'))
        
        force_fresh = request.form.get('force_fresh', '') == '1'
        
        # Cache check
        cached = None
        if not force_fresh:
            cached = svc.find_cached(topic, language)
            if cached and cached['match_type'] == 'exact':
                cached_id = cached['research']['id']
                age = svc.cache_age_minutes(cached['research'].get('completed_at'))
                flash(f'📋 Showing cached result from {age} minutes ago. Use "Research again" for fresh results.', 'info')
                return redirect(url_for('research_progress', research_id=cached_id))
        
        # Create DB record
        research_id = svc.create_research_record(
            topic=topic, language=language, depth=depth,
            focus_areas=focus_areas, provider=eff_primary,
            using_user_keys=bool(user.get(eff_primary)),
        )
        
        # Translate-only path
        if cached and cached.get('match_type') == 'english_available':
            english_research = cached['research']
            
            def run_translation():
                try:
                    asyncio.run(svc.run_translation(
                        research_id=research_id,
                        english_research=english_research,
                        language=language,
                        depth=depth,
                        resolved_keys=resolved,
                    ))
                except Exception as e:
                    svc.handle_error(research_id, e)
            
            thread = threading.Thread(target=run_translation, daemon=True)
            thread.start()
            flash(f'📋 Found cached English research — translating to {language} (much faster!)', 'info')
            return redirect(url_for('research_progress', research_id=research_id))
        
        # Full research path
        def run_research():
            try:
                asyncio.run(svc.run_research(
                    research_id=research_id,
                    topic=topic,
                    language=language,
                    depth=depth,
                    focus_areas=focus_areas,
                    resolved_keys=resolved,
                ))
            except Exception as e:
                svc.handle_error(research_id, e)
        
        thread = threading.Thread(target=run_research, daemon=True)
        thread.start()
        
        provider_msg = f"using {eff_primary.title()}"
        if eff_fallback and eff_final:
            provider_msg += f" → {eff_fallback.title()} → {eff_final.title()} fallback chain"
        elif eff_fallback:
            provider_msg += f" → {eff_fallback.title()} fallback"
        
        flash(f'Research "{topic}" has been queued! {provider_msg}', 'success')
        return redirect(url_for('research_progress', research_id=research_id))
    
    @app.route('/research/<int:research_id>')
    def research_progress(research_id):
        research = svc.get_research_detail(research_id)
        if not research:
            flash('Research not found.', 'error')
            return redirect(url_for('home'))
        
        # Collect unique sources
        all_sources = []
        seen_urls = set()
        for q in research.get('queries', []):
            for s in q.get('sources', []):
                if s['url'] not in seen_urls:
                    seen_urls.add(s['url'])
                    all_sources.append(s)
        all_sources.sort(key=lambda s: s.get('relevance_score', 0), reverse=True)
        research['all_sources'] = all_sources
        
        # Merge progress info
        progress_info = svc.progress_tracker.get(research_id, {})
        research['progress'] = progress_info.get('progress', 100 if research['status'] == 'completed' else 0)
        metadata = research.get('research_metadata') or {}
        research['provider'] = metadata.get('provider', server_primary)
        research['depth'] = metadata.get('depth', 'basic')
        lang = research.get('research_language', 'en')
        research['language'] = lang
        research['error'] = research.get('error_message', '')
        
        # Translated summary
        research['has_translations'] = False
        if lang != 'en' and research['status'] == 'completed':
            translations = metadata.get('translations', {})
            lang_data = translations.get(lang, {})
            translated_text = lang_data.get('executive_summary', {}).get('text', '')
            if translated_text:
                research['executive_summary'] = translated_text
                research['has_translations'] = True
        
        status_messages = {
            'queued': f'Queued - Waiting for processing slot',
            'in_progress': f'In Progress',
            'completed': 'Completed Successfully',
            'failed': 'Failed - Please try again',
            'temporarily_unavailable': 'Temporarily Unavailable - High API usage',
        }
        
        return render_template('progress.html',
            research=research,
            status_messages=status_messages,
            primary_provider=research.get('provider', server_primary))
    
    @app.route('/research/<int:research_id>/download')
    def download_report(research_id):
        research = svc.get_status(research_id)
        if not research or research['status'] != 'completed':
            flash('Report not available.', 'error')
            return redirect(url_for('home'))
        
        content = research.get('report_content') or research.get('executive_summary') or ''
        topic_slug = research['topic'][:40].strip().replace(' ', '_').lower()
        filename = f"research_{topic_slug}.md"
        
        return Response(content, mimetype='text/markdown',
                       headers={'Content-Disposition': f'attachment; filename="{filename}"'})
    
    @app.route('/api/research/<int:research_id>/status')
    def research_status_api(research_id):
        research = svc.get_status(research_id)
        if not research:
            return jsonify({'error': 'Research not found'}), 404
        return jsonify(research)
    
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
    
    print("🌐 Starting development server...")
    print("📌 For production, use: gunicorn app:app")
    
    port = int(os.environ.get('PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=False)
