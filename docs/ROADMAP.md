# AI Research Assistant — Roadmap

## Phase 1: Exact Match Search Cache ✅ Done

- Created `src/tools/search_cache.py` — SQLite cache, hash-based lookup, 24h TTL
- Wired into `WebSearchTool` — check cache before Tavily, store after
- Added `cache_hit` flag to `SearchResponse`
- Note: helps when identical Tavily queries repeat, but LLM generates different
  search queries each time even for the same topic — see Phase 3 for fix

---

## Phase 2: Database + UI Overhaul ✅ Done

**Goal**: Persist research, clean up architecture, improve UI.

### 2a. Move DB files to `data/` ✅ Done
### 2b. Wire database to `app.py` ✅ Done
### 2c. Move HTML to template files ✅ Done
### 2d. Research history page (`/history`)
- List past research sessions (topic, date, status, duration, language)
- Powered by existing `src/database/analytics.py`
- Click to view full results of any past research

### 2e. Show sources & citations in results
- Display sources used (title, URL, relevance score) from `Source` model
- Show follow-up questions from Tavily as "Research deeper" links

### 2f. Download report as Markdown
- "Download as Markdown" button on completed research
- Generates from `research.report_content` in DB
- Remove auto-write to `reports/` folder

### 2g. Fix & extend tests
- Fix broken existing tests (removed `SQLiteWriter` stub import, etc.)
- Add tests for: search cache, history route, download route, LLM translation provider
- Smoke test: app starts and serves pages
- Run full suite green before deployment

### Unplanned bonus (done)
- LLM translation provider (`src/tools/providers/llm_translate.py`)
- Fixed progress bar animation, markdown rendering
- Removed hardcoded Tavily API key

---

## Phase 3: Deployment (Fly.io) ✅ Done

**Goal**: Make the app publicly accessible.

**Live at: [airesearchassistant.fly.dev](https://airesearchassistant.fly.dev/)**

### Setup ✅ Done
- Dockerfile (Python 3.13, gunicorn, single worker)
- `fly.toml` configuration (ams region, persistent volume)
- GitHub Actions auto-deploy on push (`.github/workflows/fly.yml`)
- Persistent volume `ai_researcher` mounted at `/data`
- Environment variables configured as Fly.io secrets
- DB init handles existing tables gracefully

### Future: Production hardening
- CSRF protection (already have flask-wtf)
- Rate limiting on endpoints (prevent abuse)
- Basic auth or API key for access control
- Health check endpoint (already exists at `/health`)

---

## Phase 4: Topic-Level Cache ✅ Done

**Goal**: Same topic → return previous result instantly. Biggest cost saver.

### What it does
- Before running research, checks DB for completed research with same topic (normalized: lowercase, trimmed, collapsed whitespace)
- **Same topic + same language**: redirects instantly to cached result (zero API calls)
- **Same topic + different language**: finds English version, runs translation only (1 LLM call instead of full pipeline)
- **New topic**: full pipeline as before
- 24h TTL — cached results older than 24h are ignored
- "Research Again" button on results page to force fresh research (bypasses cache)

### Files changed
- `src/database/sqlite_writer.py` — added `find_cached_research(topic, language, ttl_hours)` method
- `app.py` — cache check in `submit_research()`, translate-only background path, `force_fresh` param
- `templates/progress.html` — "Research Again" button
- `tests/test_database.py` — 7 new tests for cache lookup (exact, case-insensitive, English fallback, expired, incomplete, empty report)

---

## Phase 5: Live Progress & Quick Preview ✅ Done

**Goal**: Better user engagement during the ~60s research wait.

### 5a. Live status messages ✅
- `progress_callback` on `ResearchAgent` — called at each pipeline step
- Real steps: initializing → generating_queries → searching → analyzing → writing_report → saving → translating → completed
- Step icons (🧠🔍📊📝💾🌐✅) and descriptive messages in UI
- JS polling every 3s replaces meta-refresh (no full page reload during progress)
- `/api/research/{id}/status` returns step, message, detail, preview

### 5b. Sequential search with rolling preview ✅
- Searches run sequentially (not concurrent) for steady UX updates
- After each search, Tavily AI answer appended to preview card
- ~5 preview updates, one every 3-5s during search phase
- Per-query progress messages: "🔍 Searching 2/5: quantum computing..."
- Preview stays visible during analysis with badge "Full analysis in progress..."

### 5c. Streaming LLM responses ✅
- Added `generate_stream` to all LLM clients:
  - `ImprovedLLMClient` base + OpenAI, DeepSeek, Anthropic in `rate_limiting.py` (already existed)
  - `LLMClient` base + `OpenAIClient`, `AnthropicClient` in `llm.py` (new)
- `_analyze_sources` streams analysis text into live preview (~2000 tokens, biggest call)
- `_extract_executive_summary` streams when `stream_to_preview=True` (used during report phase)
- `_generate_report` shows key findings → streams executive summary → formats final report
- Preview transitions: search results (🔍) → live analysis (📊) → writing report (📝)
- Adaptive polling: 1.2s during streaming phases, 2.5s otherwise
- Smart auto-scroll: stays at bottom unless user scrolls up
- 4 new tests: streaming analysis, streaming exec summary, non-streaming default, report streaming
- Full timeline: searches (preview grows) → analysis (streams) → report (streams) → done

---

## Phase 6: BYOK (Bring Your Own Key) ✅ Done

**Goal**: Let users provide their own API keys so they cover their own LLM/search costs. Zero cost to us, full transparency to them.

### 6a. Settings page ✅
- `/settings` route with per-provider API key inputs (Tavily, OpenAI, DeepSeek, Anthropic)
- Password-masked inputs with toggle visibility button
- "Test Connection" button per key — minimal API call to verify
- "Clear All Keys" button, "Save Keys" button
- Link in navbar ("API Keys")

### 6b. Session storage ✅
- Keys stored in Flask encrypted session cookie (never in DB)
- Persist across page loads within same browser session
- `SECRET_KEY` handles encryption

### 6c. Client creation with user keys ✅
- `_resolve_keys()` — user keys override server keys
- `_resolve_providers()` — dynamic fallback chain based on effective keys
- Both full research and translate-only paths use resolved keys
- Validates LLM + Tavily availability before starting research (redirects to settings if missing)

### 6d. UI indicators ✅
- Home page System Status shows "🔑 Your key" vs "🖥️ Server key" per provider
- Settings page shows current key status per provider
- Research metadata records which provider + whether user keys were used

### 6e. Key validation API ✅
- `/api/settings/test-key` POST endpoint
- Tests: Tavily search, OpenAI/DeepSeek models.list, Anthropic count_tokens
- Returns success/failure + details
- 9 new tests (115 total passing)

---

## Phase 7: Semantic Search Cache (sqlite-vec) ✅ Done

**Goal**: Cache hits for semantically similar queries, not just exact matches.

### Embedding providers (`src/tools/embeddings.py`) ✅
- `HashEmbedding` — zero-dependency default, hashing trick with uni/bi/trigrams, 256 dims
- `OpenAIEmbedding` — high-quality via `text-embedding-3-small` (when OpenAI key available)
- `create_embedding_provider()` — auto-selects best available
- Provider-aware similarity thresholds: 0.20 (hash) vs 0.85 (OpenAI)

### Semantic cache (`src/tools/search_cache.py`) ✅
- Rewrote with dual lookup: exact match first → vector fallback on miss
- sqlite-vec `vec0` virtual table + metadata table, same DB file
- "quantum computing basics" hits cache from "quantum computing fundamentals" (cosine 0.50)
- Respects search_depth and max_results (semantic match only when params match)
- Graceful fallback: if sqlite-vec or embedding provider unavailable, exact match still works
- Stats track exact hits, semantic hits, and misses separately

### Wiring ✅
- `app.py` creates embedding provider (auto-detects OpenAI key), passes to SearchCache
- Added `sqlite-vec>=0.1.0` and `numpy>=1.24.0` to requirements.txt + pyproject.toml
- 20 new tests (135 total passing)

---

## Phase 8: Service Layer + CLI ✅ Done

**Goal**: Extract business logic from `app.py` into a reusable service layer. Add a CLI interface that shares the same logic.

### 8a. Research service (`src/services/research_service.py`) ✅
- `ResearchService` class — all business logic in one place
- Key resolution: `resolve_keys()`, `resolve_providers()`, `key_source_label()`
- Research: `create_research_record()`, `run_research()`, `run_translation()`
- Status: `get_status()`, `get_research_detail()`, `get_history()`, `handle_error()`
- Sync wrappers for CLI: `run_research_sync()`, `run_translation_sync()`
- Cache: `find_cached()`, `cache_age_minutes()`

### 8b. Slim down `app.py` ✅
- 544 → 401 lines (–26%)
- `submit_research` route: ~150 → ~60 lines
- Routes are pure HTTP wrappers — parse request, call service, return response
- All provider selection, client creation, research orchestration in service

### 8c. CLI (`cli.py`) ✅
- `python cli.py "AI trends 2025"` — full research from terminal
- `--depth basic|advanced`, `--lang sl`, `--focus "area1,area2"`, `--output report.md`
- `--no-cache` to force fresh research
- Terminal progress bar with step icons (🧠🔍📊📝✅)
- Cache check before running (shows cached result instantly)
- Windows Unicode fix for emoji

### 8d. Tests ✅
- 21 new tests: key resolution (11), cache/status (6), record creation (1), errors (2), CLI (2)
- 156 total tests passing

---

## Future ideas (unprioritized)
- User accounts & per-user research history
- Compare two research sessions side by side
- Follow-up research ("research deeper" using Tavily follow-up questions)
- JSON API for programmatic access (FastAPI wrapper around service layer)
