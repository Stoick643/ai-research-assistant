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

## Phase 3: Deployment (Fly.io) ⬅️ In Progress

**Goal**: Make the app publicly accessible.

### Setup ✅ Done
- Dockerfile (Python 3.13, gunicorn)
- `fly.toml` configuration (ams region, persistent volume)
- GitHub Actions auto-deploy on push (`.github/workflows/fly.yml`)
- Persistent volume `ai_researcher` mounted at `/data`
- Environment variables configured as Fly.io secrets

### Remaining: Production hardening
- Fix DB init crash on deploy (table already exists — fix pushed, needs verification)
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

## Phase 5: Live Progress & Quick Preview

**Goal**: Better user engagement during the ~60s research wait.

### 4a. Live status messages
- Push real-time agent steps to the UI: "Generating search queries...",
  "Searching: quantum computing breakthroughs 2025", "Analyzing 15 sources...",
  "Synthesizing report..."
- Agent already goes through distinct phases — surface them
- Use SSE (Server-Sent Events) or polling with status messages
- Replace fake progress % (20→40→60→100) with real step-based progress

### 4b. Quick preview from Tavily
- After first search completes (~5s), show Tavily's AI answer as instant preview
- User gets something useful immediately while full LLM analysis runs
- Full report replaces preview when ready
- Preview clearly labeled: "Quick preview — full analysis in progress..."

---

## Phase 6: Semantic Search Cache (sqlite-vec)

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
