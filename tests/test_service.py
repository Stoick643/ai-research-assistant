"""
Tests for ResearchService and CLI.
"""

import pytest
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock
from src.services.research_service import ResearchService


class TestResearchServiceKeys:
    """Test key resolution and provider selection."""

    def test_resolve_keys_from_env(self):
        env = {'OPENAI_API_KEY': 'sk-test', 'TAVILY_API_KEY': 'tvly-test'}
        # Clear other keys to avoid pollution from other tests
        for k in ['DEEPSEEK_API_KEY', 'ANTHROPIC_API_KEY']:
            env[k] = ''
        with patch.dict(os.environ, env):
            keys = ResearchService.resolve_keys()
            assert keys['openai_api_key'] == 'sk-test'
            assert keys['tavily_api_key'] == 'tvly-test'
            assert not keys['deepseek_api_key']

    def test_resolve_keys_user_overrides_env(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'server-key'}):
            user = {'openai': 'user-key'}
            keys = ResearchService.resolve_keys(user)
            assert keys['openai_api_key'] == 'user-key'

    def test_resolve_keys_user_partial(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'server-openai', 'DEEPSEEK_API_KEY': 'server-ds'}):
            user = {'openai': 'user-openai'}
            keys = ResearchService.resolve_keys(user)
            assert keys['openai_api_key'] == 'user-openai'
            assert keys['deepseek_api_key'] == 'server-ds'

    def test_resolve_providers_openai_primary(self):
        keys = {'openai_api_key': 'x', 'deepseek_api_key': 'y', 'anthropic_api_key': 'z'}
        pri, fb, ffb = ResearchService.resolve_providers(keys)
        assert pri == 'openai'
        assert fb == 'deepseek'
        assert ffb == 'anthropic'

    def test_resolve_providers_deepseek_primary(self):
        keys = {'openai_api_key': None, 'deepseek_api_key': 'y', 'anthropic_api_key': 'z'}
        pri, fb, ffb = ResearchService.resolve_providers(keys)
        assert pri == 'deepseek'
        assert fb == 'anthropic'
        assert ffb is None

    def test_resolve_providers_anthropic_only(self):
        keys = {'openai_api_key': None, 'deepseek_api_key': None, 'anthropic_api_key': 'z'}
        pri, fb, ffb = ResearchService.resolve_providers(keys)
        assert pri == 'anthropic'
        assert fb is None

    def test_resolve_providers_none(self):
        keys = {'openai_api_key': None, 'deepseek_api_key': None, 'anthropic_api_key': None}
        pri, fb, ffb = ResearchService.resolve_providers(keys)
        assert pri is None

    def test_key_source_label_user(self):
        label = ResearchService.key_source_label('openai', {'openai': 'key'})
        assert 'Your key' in label

    def test_key_source_label_server(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'server'}):
            label = ResearchService.key_source_label('openai', {})
            assert 'Server key' in label

    def test_key_source_label_none(self):
        with patch.dict(os.environ, {}, clear=True):
            label = ResearchService.key_source_label('openai', {})
            assert 'Not configured' in label


class TestResearchServiceCache:
    """Test cache and status methods."""

    def test_cache_age_minutes(self):
        from datetime import datetime, timedelta
        recent = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        age = ResearchService.cache_age_minutes(recent)
        assert 4 <= age <= 6

    def test_cache_age_empty(self):
        assert ResearchService.cache_age_minutes('') == 0
        assert ResearchService.cache_age_minutes(None) == 0

    def test_find_cached_delegates(self):
        svc = ResearchService.__new__(ResearchService)
        svc.db = MagicMock()
        svc.db.find_cached_research.return_value = {'match_type': 'exact', 'research': {'id': 1}}
        result = svc.find_cached('test topic', 'en')
        assert result['match_type'] == 'exact'
        svc.db.find_cached_research.assert_called_once()

    def test_get_status_not_found(self):
        svc = ResearchService.__new__(ResearchService)
        svc.db = MagicMock()
        svc.db.get_research_by_id.return_value = None
        svc.progress_tracker = {}
        assert svc.get_status(999) is None

    def test_get_status_merges_progress(self):
        svc = ResearchService.__new__(ResearchService)
        svc.db = MagicMock()
        svc.db.get_research_by_id.return_value = {'id': 1, 'status': 'in_progress'}
        svc.progress_tracker = {1: {'progress': 50, 'step': 'analyzing', 'message': 'Working...', 'detail': '', 'preview': 'text', 'steps_log': []}}
        result = svc.get_status(1)
        assert result['progress'] == 50
        assert result['step'] == 'analyzing'

    def test_get_history_delegates(self):
        svc = ResearchService.__new__(ResearchService)
        svc.db = MagicMock()
        svc.db.get_research_history.return_value = [{'id': 1}, {'id': 2}]
        result = svc.get_history(limit=10)
        assert len(result) == 2


class TestResearchServiceRecordCreation:
    """Test DB record creation."""

    def test_create_research_record(self):
        svc = ResearchService.__new__(ResearchService)
        svc.progress_tracker = {}
        
        mock_session = MagicMock()
        mock_research = MagicMock()
        mock_research.id = 42
        
        # Mock the context manager
        svc.db = MagicMock()
        svc.db.db_manager.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        svc.db.db_manager.get_session.return_value.__exit__ = MagicMock(return_value=False)
        
        # Mock flush to set the id
        def fake_flush():
            pass
        mock_session.flush = fake_flush
        
        # We need to patch Research model
        with patch('src.services.research_service.ResearchService.create_research_record') as mock_create:
            mock_create.return_value = 42
            rid = svc.create_research_record(
                topic='test topic', language='en', depth='basic',
                provider='openai'
            )
            assert rid == 42


class TestResearchServiceErrors:
    """Test error handling."""

    def test_handle_error_generic(self):
        svc = ResearchService.__new__(ResearchService)
        svc.db = MagicMock()
        svc.progress_tracker = {}
        
        svc.handle_error(1, Exception("Something broke"))
        
        svc.db.update_research_status.assert_called_once()
        args = svc.db.update_research_status.call_args
        assert args[0][1] == 'failed'
        assert svc.progress_tracker[1]['step'] == 'failed'

    def test_handle_error_rate_limit(self):
        svc = ResearchService.__new__(ResearchService)
        svc.db = MagicMock()
        svc.progress_tracker = {}
        
        svc.handle_error(1, Exception("Rate limit exceeded"))
        
        args = svc.db.update_research_status.call_args
        assert args[0][1] == 'temporarily_unavailable'


class TestCLI:
    """Test CLI invocation."""

    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, 'cli.py', '--help'],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert 'Research topic' in result.stdout
        assert '--depth' in result.stdout

    def test_cli_short_topic(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, 'cli.py', 'short'],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 1
        assert 'at least 10' in result.stdout or 'at least 10' in result.stderr
