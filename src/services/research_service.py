"""
Research service — all business logic for running research.

Used by both the Flask web app and the CLI.
No HTTP or Flask dependencies here.
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
import structlog

logger = structlog.get_logger()


class ResearchService:
    """
    Core research orchestration service.
    
    Encapsulates: key resolution, provider selection, LLM client creation,
    agent setup, research execution, translation, caching, and DB persistence.
    """
    
    def __init__(self, db=None):
        """
        Args:
            db: SQLiteWriter instance (created automatically if None)
        """
        if db is None:
            from src.database.sqlite_writer import SQLiteWriter
            db = SQLiteWriter()
        self.db = db
        self.progress_tracker: Dict[int, Dict[str, Any]] = {}
        self.logger = logger.bind(component="research_service")
    
    # ── Key & provider resolution ────────────────────────────────────
    
    @staticmethod
    def resolve_keys(user_keys: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Resolve effective API keys. User keys override server (env) keys.
        
        Args:
            user_keys: dict with optional keys: openai, deepseek, anthropic, tavily
        
        Returns:
            Dict with resolved keys: openai_api_key, deepseek_api_key, anthropic_api_key, tavily_api_key
        """
        user = user_keys or {}
        return {
            'openai_api_key': user.get('openai') or os.environ.get('OPENAI_API_KEY'),
            'deepseek_api_key': user.get('deepseek') or os.environ.get('DEEPSEEK_API_KEY'),
            'anthropic_api_key': user.get('anthropic') or os.environ.get('ANTHROPIC_API_KEY'),
            'tavily_api_key': user.get('tavily') or os.environ.get('TAVILY_API_KEY'),
        }
    
    @staticmethod
    def resolve_providers(keys: Dict[str, str]):
        """
        Determine provider fallback chain from resolved keys.
        
        Returns:
            (primary, fallback, final_fallback) — any can be None
        """
        has_o = bool(keys.get('openai_api_key'))
        has_d = bool(keys.get('deepseek_api_key'))
        has_a = bool(keys.get('anthropic_api_key'))
        
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
    
    @staticmethod
    def key_source_label(provider: str, user_keys: Optional[Dict[str, str]] = None) -> str:
        """Return label showing whether user key or server key is active."""
        user = user_keys or {}
        if user.get(provider):
            return "🔑 Your key"
        elif os.environ.get(f'{provider.upper()}_API_KEY'):
            return "🖥️ Server key"
        else:
            return "❌ Not configured"
    
    def _create_llm_client(self, keys, primary, fallback, final_fallback):
        """Create an LLM client with fallback chain."""
        from src.utils.rate_limiting import create_improved_llm_client
        return create_improved_llm_client(
            primary_provider=primary,
            fallback_provider=fallback,
            final_fallback_provider=final_fallback,
            deepseek_api_key=keys['deepseek_api_key'],
            openai_api_key=keys['openai_api_key'],
            anthropic_api_key=keys['anthropic_api_key'],
            deepseek_model="deepseek-chat",
            openai_model="gpt-4",
        )
    
    def _create_search_tool(self, keys):
        """Create web search tool with semantic cache."""
        from src.tools.web_search import WebSearchTool
        from src.tools.search_cache import SearchCache
        from src.tools.embeddings import create_embedding_provider
        
        embedding_provider = create_embedding_provider(
            openai_api_key=keys.get('openai_api_key')
        )
        search_cache = SearchCache(embedding_provider=embedding_provider)
        return WebSearchTool(api_key=keys['tavily_api_key'], search_cache=search_cache)
    
    def _make_progress_callback(self, research_id: int) -> Callable:
        """Create a progress callback that updates the tracker."""
        def on_progress(step, progress, message, detail='', preview=''):
            tracker = self.progress_tracker.get(research_id, {})
            tracker['progress'] = progress
            tracker['step'] = step
            tracker['message'] = message
            tracker['detail'] = detail
            if preview:
                tracker['preview'] = preview
            if 'steps_log' not in tracker:
                tracker['steps_log'] = []
            tracker['steps_log'].append({
                'step': step, 'message': message, 'progress': progress
            })
            self.progress_tracker[research_id] = tracker
        return on_progress
    
    # ── Cache check ──────────────────────────────────────────────────
    
    def find_cached(self, topic: str, language: str, ttl_hours: int = 24) -> Optional[Dict]:
        """
        Check for cached research result.
        
        Returns:
            dict with 'match_type' ('exact' or 'english_available') and 'research', or None
        """
        return self.db.find_cached_research(topic, language, ttl_hours=ttl_hours)
    
    @staticmethod
    def cache_age_minutes(completed_at_iso: str) -> int:
        """Return how many minutes ago a cached result was completed."""
        try:
            if not completed_at_iso:
                return 0
            completed = datetime.fromisoformat(completed_at_iso)
            return max(1, int((datetime.utcnow() - completed).total_seconds() / 60))
        except (ValueError, TypeError):
            return 0
    
    # ── Research execution ───────────────────────────────────────────
    
    def create_research_record(
        self, topic: str, language: str, depth: str,
        focus_areas: Optional[str] = None,
        provider: Optional[str] = None,
        using_user_keys: bool = False,
    ) -> int:
        """Create a research record in the database. Returns research_id."""
        from src.database.models import Research
        
        with self.db.db_manager.get_session() as session:
            research = Research(
                topic=topic,
                focus_areas=focus_areas.split(',') if focus_areas else [],
                agent_name="MultiLangWebResearcher",
                status='queued',
                research_language=language,
                research_metadata={
                    'depth': depth,
                    'provider': provider,
                    'using_user_keys': using_user_keys,
                },
            )
            session.add(research)
            session.flush()
            research_id = research.id
        
        self.progress_tracker[research_id] = {'progress': 0}
        return research_id
    
    async def run_research(
        self,
        research_id: int,
        topic: str,
        language: str = 'en',
        depth: str = 'basic',
        focus_areas: Optional[str] = None,
        resolved_keys: Optional[Dict[str, str]] = None,
        user_keys: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full research pipeline (async).
        
        Args:
            research_id: DB record ID (created via create_research_record)
            topic: Research topic
            language: Target language code
            depth: Search depth ('basic' or 'advanced')
            focus_areas: Comma-separated focus areas
            resolved_keys: Pre-resolved keys (if already computed)
            user_keys: Raw user keys (resolved if resolved_keys not given)
        
        Returns:
            Research result dict
        """
        from src.utils.rate_limiting import research_queue
        
        keys = resolved_keys or self.resolve_keys(user_keys)
        primary, fallback, final_fb = self.resolve_providers(keys)
        
        if not primary:
            raise ValueError("No LLM provider available")
        if not keys.get('tavily_api_key'):
            raise ValueError("No Tavily API key available")
        
        on_progress = self._make_progress_callback(research_id)
        
        async with research_queue:
            self.db.update_research_status(research_id, 'in_progress')
            on_progress('initializing', 5, 'Initializing research pipeline...', f'Topic: {topic[:80]}')
            
            # Build components
            from src.tools.report_writer import MarkdownWriter
            from src.agents.multilang_research_agent import MultiLanguageResearchAgent
            
            llm_client = self._create_llm_client(keys, primary, fallback, final_fb)
            web_search = self._create_search_tool(keys)
            report_writer = MarkdownWriter()
            
            agent = MultiLanguageResearchAgent(
                name="MultiLangWebResearcher",
                llm_client=llm_client,
                web_search_tool=web_search,
                report_writer=report_writer,
                default_language='en',
                target_languages=[language] if language != 'en' else ['en'],
                enable_translation=True,
            )
            agent.progress_callback = on_progress
            
            # Run
            if language != 'en':
                result = await agent.conduct_multilang_research(
                    topic=topic,
                    focus_areas=focus_areas.split(',') if focus_areas else None,
                    target_languages=[language, 'en'],
                    search_depth=depth,
                )
                on_progress('translating', 95, f'Translating to {language.upper()}...', '')
            else:
                result = await agent.conduct_research(
                    topic=topic,
                    focus_areas=focus_areas.split(',') if focus_areas else None,
                    search_depth=depth,
                )
            
            on_progress('completed', 100, 'Research complete!', '')
            
            # Persist results
            self._save_research_result(research_id, result, depth, primary)
            
            return result
    
    async def run_translation(
        self,
        research_id: int,
        english_research: Dict[str, Any],
        language: str,
        depth: str = 'basic',
        resolved_keys: Optional[Dict[str, str]] = None,
        user_keys: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Translate an existing English research result to another language.
        
        Args:
            research_id: DB record ID for the new (translated) research
            english_research: The cached English research dict
            language: Target language code
            depth: Original search depth
            resolved_keys: Pre-resolved API keys
            user_keys: Raw user keys
        """
        keys = resolved_keys or self.resolve_keys(user_keys)
        primary, fallback, final_fb = self.resolve_providers(keys)
        
        on_progress = self._make_progress_callback(research_id)
        
        self.db.update_research_status(research_id, 'in_progress')
        on_progress('initializing', 20,
                    'Found cached English research — preparing translation...',
                    f'Translating to {language.upper()}',
                    preview=english_research.get('executive_summary', '')[:500])
        
        from src.tools.translation import TranslationTool
        
        llm_client = self._create_llm_client(keys, primary, fallback, final_fb)
        translator = TranslationTool(llm_client=llm_client)
        
        on_progress('translating', 50,
                    f'Translating report to {language.upper()}...',
                    'Translating main report content')
        
        en_report = english_research.get('report_content', '')
        report_result = await translator.translate(en_report, language, source_language='en')
        translated_report = report_result.translated_text
        
        on_progress('translating', 80,
                    f'Translating summary to {language.upper()}...',
                    'Almost done')
        
        en_summary = english_research.get('executive_summary', '')
        if en_summary:
            summary_result = await translator.translate(en_summary, language, source_language='en')
            translated_summary = summary_result.translated_text
        else:
            translated_summary = ''
        
        # Save translated result
        from src.database.models import Research as ResearchModel
        with self.db.db_manager.get_session() as session:
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
                    'provider': primary,
                    'cached_from': english_research['id'],
                    'cache_type': 'translate_only',
                }
        
        on_progress('completed', 100, 'Translation complete!', '')
    
    def _save_research_result(self, research_id: int, result: Dict, depth: str, provider: str):
        """Save research result to database."""
        from src.database.models import Research as ResearchModel
        
        with self.db.db_manager.get_session() as session:
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
                    'provider': provider,
                    'language_metadata': result.get('language_metadata', {}),
                    'translations': result.get('translations', {}),
                }
                rec.translation_enabled = bool(result.get('translations'))
    
    # ── Status & retrieval ───────────────────────────────────────────
    
    def get_status(self, research_id: int) -> Optional[Dict[str, Any]]:
        """Get research status with progress info merged."""
        research = self.db.get_research_by_id(research_id)
        if not research:
            return None
        
        progress_info = self.progress_tracker.get(research_id, {})
        research['progress'] = progress_info.get('progress', 100 if research['status'] == 'completed' else 0)
        research['step'] = progress_info.get('step', 'completed' if research['status'] == 'completed' else 'queued')
        research['step_message'] = progress_info.get('message', '')
        research['step_detail'] = progress_info.get('detail', '')
        research['preview'] = progress_info.get('preview', '')
        research['steps_log'] = progress_info.get('steps_log', [])
        
        return research
    
    def get_research_detail(self, research_id: int) -> Optional[Dict[str, Any]]:
        """Get full research with queries/sources for display."""
        research = self.db.get_research_with_details(research_id)
        if not research:
            research = self.db.get_research_by_id(research_id)
        return research
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """Get research history."""
        return self.db.get_research_history(limit=limit)
    
    def handle_error(self, research_id: int, error: Exception):
        """Handle research/translation errors — update DB and progress."""
        error_msg = str(error)
        if 'quota' in error_msg.lower() or 'rate limit' in error_msg.lower():
            status = 'temporarily_unavailable'
            friendly = "Service temporarily unavailable due to high demand. Please try again in a few minutes."
        else:
            status = 'failed'
            friendly = f"Research failed: {error_msg}"
        
        self.db.update_research_status(research_id, status, friendly)
        self.progress_tracker[research_id] = {
            'progress': 0, 'step': 'failed',
            'message': friendly, 'detail': '',
        }
    
    # ── Sync wrappers (for CLI) ──────────────────────────────────────
    
    def run_research_sync(self, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper around run_research."""
        return asyncio.run(self.run_research(**kwargs))
    
    def run_translation_sync(self, **kwargs) -> None:
        """Synchronous wrapper around run_translation."""
        asyncio.run(self.run_translation(**kwargs))
