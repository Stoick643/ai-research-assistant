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

## Phase 6: BYOK (Bring Your Own Key) ⬅️ Next

**Goal**: Let users provide their own API keys so they cover their own LLM/search costs. Zero cost to us, full transparency to them.

### 6a. Settings page
- New `/settings` route with form for API keys: OpenAI, Anthropic, DeepSeek, Tavily
- Clean UI with per-provider sections, password-masked inputs
- "Test Connection" button per key — quick API ping to verify it works
- "Clear All Keys" button to wipe stored keys
- Link to settings from navbar

### 6b. Session storage
- Store keys in Flask encrypted session cookie (never in DB)
- Keys persist across page loads but not across browsers/devices
- `SECRET_KEY` already configured — session encryption works out of the box

### 6c. Client creation with user keys
- Modify `app.py` research pipeline to prefer user keys when present
- Fall back to server keys when user hasn't provided their own
- Build provider fallback chain dynamically based on which keys are available
- Works for both full research and translate-only paths

### 6d. UI indicators
- Home page shows "Using your OpenAI key" vs "Using server key" per provider
- Progress page shows which keys powered the research
- Settings page shows which keys are currently stored (masked)

### 6e. Key validation API
- `/api/settings/test-key` endpoint — tests a single provider key
- Returns success/failure + model info (e.g., "gpt-4 access confirmed")
- Called by "Test Connection" button via JS

---

## Phase 7: Semantic Search Cache (sqlite-vec)

**Goal**: Cache hits for semantically similar queries, not just exact matches.

### Research needed
- Evaluate `sqlite-vec` as embedded vector DB
- Choose embedding approach: OpenAI embeddings API vs lightweight local model
- Define similarity threshold (configurable)

### Changes to `src/tools/search_cache.py`
- On exact cache miss → do vector similarity search against stored query embeddings
- "quantum computing basics" hits cache from "introduction to quantum computing"
- Fallback: if sqlite-vec unavailable, exact match still works

### New dependency
- `sqlite-vec` package
- Embedding provider (TBD)

---

## Future ideas (unprioritized)
- User accounts & per-user research history
- Compare two research sessions side by side
- Follow-up research ("research deeper" using Tavily follow-up questions)
- JSON API for programmatic access
- CLI and web share a clean service layer
