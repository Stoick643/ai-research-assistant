# AI Research Assistant — Roadmap

## Phase 1: Exact Match Search Cache ✅ Done

- Created `src/tools/search_cache.py` — SQLite cache, hash-based lookup, 24h TTL
- Wired into `WebSearchTool` — check cache before Tavily, store after
- Added `cache_hit` flag to `SearchResponse`
- Note: helps when identical Tavily queries repeat, but LLM generates different
  search queries each time even for the same topic — see Phase 3 for fix

---

## Phase 2: Database + UI Overhaul ⬅️ In Progress

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

## Phase 3: Deployment (Fly.io)

**Goal**: Make the app publicly accessible.

### Setup
- Create `Dockerfile`
- Create `fly.toml` configuration
- Persistent volume for `data/research_history.db`
- Cache DBs can live on ephemeral storage
- Environment variables for API keys (Fly.io secrets)

### Production hardening
- CSRF protection (already have flask-wtf)
- Rate limiting on endpoints (prevent abuse)
- Basic auth or API key for access control
- Health check endpoint (already exists at `/health`)

---

## Phase 4: Topic-Level Cache

**Goal**: Same topic → return previous result instantly. Biggest cost saver.

### The problem
- User submits same topic twice (e.g. same query in English then Slovenian)
- LLM generates different search queries each time → query-level cache misses
- Full pipeline runs again: 5 Tavily calls + multiple LLM calls = wasted time & money

### Solution: cache at the topic level
- Before starting research, check `research_history.db` for a completed research
  with the same (or very similar) topic text
- Exact match: normalize topic (lowercase, strip whitespace) → lookup in DB
- If found and fresh (within TTL, e.g. 24h): return cached result immediately
- For translated requests: reuse English research, only run translation step
- UI: indicate "Served from previous research" with option to "Research again"

### Implementation
- Add check in `app.py` `submit_research()` before spawning background thread
- Query `Research` table for matching topic + status=completed
- If translating to new language: reuse English analysis, run translation only
- Configurable TTL (default 24h, same as search cache)

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
