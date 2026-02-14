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
from datetime import datetime, timedelta
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

def _cache_age_minutes(completed_at_iso: str) -> int:
    """Return how many minutes ago a cached result was completed."""
    try:
        if not completed_at_iso:
            return 0
        completed = datetime.fromisoformat(completed_at_iso)
        return max(1, int((datetime.utcnow() - completed).total_seconds() / 60))
    except (ValueError, TypeError):
        return 0


def create_production_app():
    """Create production-optimized Flask app."""
    
    from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
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
    
    # ── BYOK helpers ──────────────────────────────────────────────────
    
    def _get_user_keys():
        """Get user-provided API keys from session."""
        return {
            'openai': session.get('openai_api_key'),
            'deepseek': session.get('deepseek_api_key'),
            'anthropic': session.get('anthropic_api_key'),
            'tavily': session.get('tavily_api_key'),
        }
    
    def _resolve_keys():
        """Resolve effective API keys: user keys override server keys."""
        user = _get_user_keys()
        return {
            'openai_api_key': user['openai'] or os.environ.get('OPENAI_API_KEY'),
            'deepseek_api_key': user['deepseek'] or os.environ.get('DEEPSEEK_API_KEY'),
            'anthropic_api_key': user['anthropic'] or os.environ.get('ANTHROPIC_API_KEY'),
            'tavily_api_key': user['tavily'] or os.environ.get('TAVILY_API_KEY'),
        }
    
    def _resolve_providers(keys):
        """Determine provider chain based on resolved keys."""
        has_o = bool(keys['openai_api_key'])
        has_d = bool(keys['deepseek_api_key'])
        has_a = bool(keys['anthropic_api_key'])
        
        if has_o:
            pri = "openai"
            if has_d and has_a:
                fb, ffb = "deepseek", "anthropic"
            elif has_d:
                fb, ffb = "deepseek", None
            elif has_a:
                fb, ffb = "anthropic", None
            else:
                fb, ffb = None, None
        elif has_d:
            pri = "deepseek"
            fb = "anthropic" if has_a else None
            ffb = None
        elif has_a:
            pri = "anthropic"
            fb, ffb = None, None
        else:
            pri, fb, ffb = None, None, None
        
        return pri, fb, ffb
    
    def _key_source_label(provider):
        """Return label showing whether user key or server key is active."""
        user = _get_user_keys()
        if user.get(provider):
            return "🔑 Your key"
        elif os.environ.get(f'{provider.upper()}_API_KEY'):
            return "🖥️ Server key"
        else:
            return "❌ Not configured"
    
    # ── Routes ─────────────────────────────────────────────────────────
    
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
        # Resolve effective providers based on user keys
        resolved = _resolve_keys()
        eff_pri, eff_fb, eff_ffb = _resolve_providers(resolved)
        
        # Build cost status reflecting effective keys
        user = _get_user_keys()
        any_user_keys = any(v for v in user.values())
        if any_user_keys:
            eff_cost = "🔑 Using your API keys"
        else:
            eff_cost = cost_status
        
        return render_template('home.html',
            primary_provider=eff_pri or primary_provider,
            fallback_provider=eff_fb or fallback_provider,
            final_fallback=eff_ffb or final_fallback,
            cost_status=eff_cost,
            key_sources={
                'primary': _key_source_label(eff_pri or primary_provider),
                'tavily': _key_source_label('tavily'),
            })
    
    @app.route('/history')
    def history():
        """Show research history."""
        researches = db.get_research_history(limit=100)
        return render_template('history.html', researches=researches)
    
    @app.route('/settings')
    def settings():
        """API key settings page."""
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
        """Save user API keys to session."""
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
        """Clear all user API keys from session."""
        for p in ['tavily', 'openai', 'deepseek', 'anthropic']:
            session.pop(f'{p}_api_key', None)
        flash('🗑️ All your API keys have been cleared. Using server defaults.', 'info')
        return redirect(url_for('settings'))
    
    @app.route('/api/settings/test-key', methods=['POST'])
    def test_api_key():
        """Test an API key by making a minimal API call."""
        import asyncio as _asyncio
        
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
                # Minimal call — count tokens is cheapest
                resp = client.messages.count_tokens(
                    model="claude-3-sonnet-20240229",
                    messages=[{"role": "user", "content": "hi"}]
                )
                return jsonify({'success': True, 'message': f'Anthropic key is valid ✓'})
            
            else:
                return jsonify({'success': False, 'message': f'Unknown provider: {provider}'})
        
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
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
        
        # Resolve API keys (user keys override server keys)
        # Must capture here — session not available in background thread
        resolved = _resolve_keys()
        eff_primary, eff_fallback, eff_final = _resolve_providers(resolved)
        
        if not eff_primary:
            flash('❌ No LLM provider available. Please add at least one API key in Settings.', 'error')
            return redirect(url_for('settings'))
        
        if not resolved['tavily_api_key']:
            flash('❌ No Tavily API key available. Please add one in Settings.', 'error')
            return redirect(url_for('settings'))
        
        force_fresh = request.form.get('force_fresh', '') == '1'
        
        # --- Topic-level cache check ---
        if not force_fresh:
            cached = db.find_cached_research(topic, language, ttl_hours=24)
            
            if cached and cached['match_type'] == 'exact':
                # Same topic + same language → return instantly
                cached_id = cached['research']['id']
                age_mins = _cache_age_minutes(cached['research'].get('completed_at'))
                flash(f'📋 Showing cached result from {age_mins} minutes ago. Use "Research again" for fresh results.', 'info')
                return redirect(url_for('research_progress', research_id=cached_id))
            
            if cached and cached['match_type'] == 'english_available':
                # English version exists → translate only (handled below with flag)
                english_research = cached['research']
        else:
            cached = None
        
        # Create research record in database
        from src.database.models import Research
        with db.db_manager.get_session() as session:
            research = Research(
                topic=topic,
                focus_areas=focus_areas.split(',') if focus_areas else [],
                agent_name="MultiLangWebResearcher",
                status='queued',
                research_language=language,
                research_metadata={'depth': depth, 'provider': eff_primary, 'using_user_keys': bool(_get_user_keys().get(eff_primary))},
            )
            session.add(research)
            session.flush()
            research_id = research.id
        
        # Track progress in memory (transient)
        progress_tracker[research_id] = {'progress': 0}
        
        # --- Translate-only path: English result exists, just translate ---
        translate_only = (cached and cached.get('match_type') == 'english_available')
        
        if translate_only:
            def run_translation_only():
                try:
                    async def translate_cached():
                        db.update_research_status(research_id, 'in_progress')
                        progress_tracker[research_id] = {
                            'progress': 20, 'step': 'initializing',
                            'message': 'Found cached English research — preparing translation...',
                            'detail': f'Translating to {language.upper()}',
                            'preview': english_research.get('executive_summary', '')[:500],
                        }
                        
                        from src.tools.translation import TranslationTool
                        
                        llm_client = create_improved_llm_client(
                            primary_provider=eff_primary,
                            fallback_provider=eff_fallback,
                            final_fallback_provider=eff_final,
                            deepseek_api_key=resolved['deepseek_api_key'],
                            openai_api_key=resolved['openai_api_key'],
                            anthropic_api_key=resolved['anthropic_api_key'],
                            deepseek_model="deepseek-chat",
                            openai_model="gpt-4"
                        )
                        
                        translator = TranslationTool(llm_client=llm_client)
                        progress_tracker[research_id].update({
                            'progress': 50, 'step': 'translating',
                            'message': f'Translating report to {language.upper()}...',
                            'detail': 'Translating main report content',
                        })
                        
                        # Translate the English report content
                        en_report = english_research.get('report_content', '')
                        report_result = await translator.translate(en_report, language, source_language='en')
                        translated_report = report_result.translated_text
                        
                        progress_tracker[research_id].update({
                            'progress': 80, 'step': 'translating',
                            'message': f'Translating summary to {language.upper()}...',
                            'detail': 'Almost done',
                        })
                        
                        # Also translate executive summary
                        en_summary = english_research.get('executive_summary', '')
                        if en_summary:
                            summary_result = await translator.translate(en_summary, language, source_language='en')
                            translated_summary = summary_result.translated_text
                        else:
                            translated_summary = ''
                        
                        # Update the new research record with translated content
                        with db.db_manager.get_session() as session:
                            from src.database.models import Research as ResearchModel
                            rec = session.query(ResearchModel).get(research_id)
                            if rec:
                                rec.status = 'completed'
                                rec.completed_at = datetime.utcnow()
                                rec.processing_time = (datetime.utcnow() - rec.started_at).total_seconds()
                                rec.executive_summary = translated_summary
                                rec.detailed_analysis = translated_report
                                rec.report_content = translated_report
                                rec.total_queries = english_research.get('total_queries', 0)
                                rec.total_sources = english_research.get('total_sources', 0)
                                rec.translation_enabled = True
                                rec.research_metadata = {
                                    'depth': depth,
                                    'provider': primary_provider,
                                    'cached_from': english_research['id'],
                                    'cache_type': 'translate_only',
                                }
                        
                        progress_tracker[research_id].update({
                            'progress': 100, 'step': 'completed',
                            'message': 'Translation complete!', 'detail': '',
                        })
                    
                    asyncio.run(translate_cached())
                    
                except Exception as e:
                    db.update_research_status(research_id, 'failed', f"Translation failed: {str(e)}")
                    progress_tracker[research_id].update({
                        'progress': 0, 'step': 'failed',
                        'message': f'Translation failed: {str(e)}', 'detail': '',
                    })
            
            thread = threading.Thread(target=run_translation_only)
            thread.daemon = True
            thread.start()
            
            flash(f'📋 Found cached English research — translating to {language} (much faster!)', 'info')
            return redirect(url_for('research_progress', research_id=research_id))
        
        # Start full background research
        def run_research():
            try:
                async def research_with_queue():
                    async with research_queue:
                        db.update_research_status(research_id, 'in_progress')
                        
                        # Progress callback — agent calls this at each pipeline step
                        def on_progress(step, progress, message, detail='', preview=''):
                            tracker = progress_tracker.get(research_id, {})
                            tracker['progress'] = progress
                            tracker['step'] = step
                            tracker['message'] = message
                            tracker['detail'] = detail
                            if preview:
                                tracker['preview'] = preview
                            # Keep log of completed steps
                            if 'steps_log' not in tracker:
                                tracker['steps_log'] = []
                            tracker['steps_log'].append({'step': step, 'message': message, 'progress': progress})
                            progress_tracker[research_id] = tracker
                        
                        on_progress('initializing', 5, 'Initializing research pipeline...', f'Topic: {topic[:80]}')
                        
                        # Import research components
                        from src.tools.web_search import WebSearchTool
                        from src.tools.search_cache import SearchCache
                        from src.tools.report_writer import MarkdownWriter
                        from src.agents.multilang_research_agent import MultiLanguageResearchAgent
                        
                        # Initialize enhanced LLM client (uses user keys if provided)
                        llm_client = create_improved_llm_client(
                            primary_provider=eff_primary,
                            fallback_provider=eff_fallback,
                            final_fallback_provider=eff_final,
                            deepseek_api_key=resolved['deepseek_api_key'],
                            openai_api_key=resolved['openai_api_key'],
                            anthropic_api_key=resolved['anthropic_api_key'],
                            deepseek_model="deepseek-chat",
                            openai_model="gpt-4"
                        )
                        
                        from src.tools.embeddings import create_embedding_provider
                        embedding_provider = create_embedding_provider(
                            openai_api_key=resolved.get('openai_api_key')
                        )
                        search_cache = SearchCache(embedding_provider=embedding_provider)
                        web_search = WebSearchTool(api_key=resolved['tavily_api_key'], search_cache=search_cache)
                        report_writer = MarkdownWriter()
                        
                        # Create multilingual research agent with progress callback
                        agent = MultiLanguageResearchAgent(
                            name="MultiLangWebResearcher",
                            llm_client=llm_client,
                            web_search_tool=web_search,
                            report_writer=report_writer,
                            default_language='en',
                            target_languages=[language] if language != 'en' else ['en'],
                            enable_translation=True
                        )
                        agent.progress_callback = on_progress
                        
                        # Run research
                        if language != 'en':
                            result = await agent.conduct_multilang_research(
                                topic=topic,
                                focus_areas=focus_areas.split(',') if focus_areas else None,
                                target_languages=[language, 'en'],
                                search_depth=depth
                            )
                            on_progress('translating', 95, f'Translating to {language.upper()}...', '')
                        else:
                            result = await agent.conduct_research(
                                topic=topic,
                                focus_areas=focus_areas.split(',') if focus_areas else None,
                                search_depth=depth
                            )
                        
                        on_progress('completed', 100, 'Research complete!', '')
                        
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
                progress_tracker[research_id] = {
                    'progress': 0, 'step': 'failed',
                    'message': friendly_error, 'detail': '',
                }
        
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
        
        research = db.get_research_with_details(research_id)
        if not research:
            # Might be in-progress (not yet written to DB with details)
            research = db.get_research_by_id(research_id)
        if not research:
            flash('Research not found.', 'error')
            return redirect(url_for('home'))
        
        # Collect unique sources across all queries, sorted by relevance
        all_sources = []
        seen_urls = set()
        for q in research.get('queries', []):
            for s in q.get('sources', []):
                if s['url'] not in seen_urls:
                    seen_urls.add(s['url'])
                    all_sources.append(s)
        all_sources.sort(key=lambda s: s.get('relevance_score', 0), reverse=True)
        research['all_sources'] = all_sources
        
        # Merge transient progress info
        progress_info = progress_tracker.get(research_id, {})
        research['progress'] = progress_info.get('progress', 100 if research['status'] == 'completed' else 0)
        metadata = research.get('research_metadata') or {}
        research['provider'] = metadata.get('provider', primary_provider)
        research['depth'] = metadata.get('depth', 'basic')
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
        
        return render_template('progress.html',
            research=research,
            status_messages=status_messages,
            primary_provider=primary_provider)
    
    @app.route('/research/<int:research_id>/download')
    def download_report(research_id):
        """Download research report as Markdown."""
        from flask import Response
        
        research = db.get_research_by_id(research_id)
        if not research or research['status'] != 'completed':
            flash('Report not available.', 'error')
            return redirect(url_for('home'))
        
        content = research.get('report_content') or research.get('executive_summary') or ''
        topic_slug = research['topic'][:40].strip().replace(' ', '_').lower()
        filename = f"research_{topic_slug}.md"
        
        return Response(
            content,
            mimetype='text/markdown',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    
    @app.route('/api/research/<int:research_id>/status')
    def research_status_api(research_id):
        """Get research status as JSON with live progress details."""
        research = db.get_research_by_id(research_id)
        if not research:
            return jsonify({'error': 'Research not found'}), 404
        
        # Merge transient progress info
        progress_info = progress_tracker.get(research_id, {})
        research['progress'] = progress_info.get('progress', 100 if research['status'] == 'completed' else 0)
        research['step'] = progress_info.get('step', 'completed' if research['status'] == 'completed' else 'queued')
        research['step_message'] = progress_info.get('message', '')
        research['step_detail'] = progress_info.get('detail', '')
        research['preview'] = progress_info.get('preview', '')
        research['steps_log'] = progress_info.get('steps_log', [])
        
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