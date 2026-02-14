# AI Research Assistant — Roadmap

## Phase 1: Exact Match Search Cache ✅ Done

**Goal**: Avoid duplicate Tavily API calls for identical queries. Save money immediately.

- Created `src/tools/search_cache.py` — SQLite cache, hash-based lookup, 24h TTL
- Wired into `WebSearchTool` — check cache before Tavily, store after
- Added `cache_hit` flag to `SearchResponse`

---

## Phase 2: Database + UI Overhaul ⬅️ Next

**Goal**: Persist research, clean up architecture, improve UI.

### 2a. Move DB files to `data/`
- `data/research_history.db` — persistent
- `data/cache/search_cache.db` — ephemeral (24h TTL)
- `data/cache/translation_cache.db` — ephemeral (increase TTL to 30 days)
- Update default paths in: `sqlite_writer.py`, `analytics.py`, `database.py`, `search_cache.py`, `translation_cache.py`
- Update `.gitignore`
- Delete dead `SQLiteWriter` stub in `report_writer.py`

### 2b. Wire database to `app.py`
- Replace in-memory `research_storage = {}` with reads/writes via `src/database/`
- Research survives app restarts
- Clean separation: `app.py` is a thin UI layer, all business logic goes through agents/database

### 2c. Move HTML to template files
- Extract inline `render_template_string()` HTML from `app.py` into `templates/`
- `templates/base.html` — shared layout (navbar, Bootstrap, marked.js)
- `templates/home.html` — research form
- `templates/progress.html` — research progress/results
- `templates/history.html` — new, see 2d

### 2d. Research history page (`/history`)
- List past research sessions (topic, date, status, duration, language)
- Powered by existing `src/database/analytics.py`
- Click to view full results of any past research
- Cache hit stats (e.g. "3/5 queries from cache")

### 2e. Show sources & citations in results
- Display sources used (title, URL, relevance score) from `Source` model
- Show follow-up questions from Tavily as "Research deeper" links

### 2f. Download report as Markdown
- "Download as Markdown" button on completed research
- Generates from `research.report_content` in DB — no more auto-writing to `reports/`
- Remove auto-write to `reports/` folder (keep folder for manual exports)

---

## Phase 3: Semantic Search Cache (sqlite-vec)

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

## Phase 4: Deployment (Fly.io)

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

## Future ideas (unprioritized)
- User accounts & per-user research history
- Compare two research sessions side by side
- Follow-up research ("research deeper" using Tavily follow-up questions)
- JSON API for programmatic access
- CLI and web share a clean service layer
