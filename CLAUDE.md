# AI Research Assistant

An AI-powered research assistant that conducts web searches, synthesizes findings using LLMs, and generates comprehensive multi-language reports.

## Project Structure

```
├── app.py                          # Flask web app (thin HTTP layer)
├── cli.py                          # CLI interface
├── src/
│   ├── services/                   # Business logic layer
│   │   └── research_service.py     # Core research orchestration
│   ├── agents/                     # Agent implementations
│   │   ├── base.py                 # Base agent class
│   │   ├── reasoning.py            # Step-by-step reasoning agent
│   │   ├── reactive.py             # Event-driven agent with tools
│   │   ├── research_agent.py       # Web research agent (streaming)
│   │   └── multilang_research_agent.py  # Multi-language research
│   ├── tools/                      # Tool integrations
│   │   ├── web_search.py           # Tavily web search
│   │   ├── search_cache.py         # Exact + semantic search cache
│   │   ├── embeddings.py           # Embedding providers (hash, OpenAI)
│   │   ├── report_writer.py        # Markdown report generation
│   │   ├── translation.py          # Translation framework
│   │   ├── translation_cache.py    # Translation caching
│   │   ├── language_detection.py   # Language detection
│   │   └── providers/              # Translation providers
│   ├── database/                   # Data persistence
│   │   ├── database.py             # Database setup
│   │   ├── models.py               # SQLAlchemy models
│   │   ├── sqlite_writer.py        # Research history writer
│   │   └── analytics.py            # Research analytics
│   └── utils/                      # Utilities
│       ├── llm.py                  # LLM client abstractions (OpenAI, Anthropic)
│       ├── rate_limiting.py        # Rate limiting, fallback chains, streaming, request queuing
│       ├── config.py               # Configuration management
│       └── logger.py               # Structured logging
├── templates/                      # Flask HTML templates
├── examples/                       # Example agent scripts
├── tests/                          # Test suite (pytest, 156 tests)
├── docs/                           # Documentation & roadmap
└── pyproject.toml                  # Dependencies & project config
```

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with API keys (at least one LLM provider + Tavily)
```

## Running

```bash
# Web UI (development)
python app.py

# Web UI (production)
gunicorn app:app --bind 0.0.0.0:5003 --workers 2 --timeout 120

# CLI
python cli.py "quantum computing trends 2025"
python cli.py "AI safety" --depth advanced --lang sl
python cli.py "climate change" --focus "ocean,arctic" --output report.md
python cli.py "topic" --no-cache    # Force fresh research
```

## Key Commands

```bash
pytest                              # Run tests (156 tests)
pytest --cov=src                    # Tests with coverage
black . && isort .                  # Format code
mypy src/                           # Type checking
```

## Architecture

- **Service layer**: `src/services/research_service.py` — all business logic (key resolution, research orchestration, caching, DB persistence)
- **Web UI**: `app.py` — thin Flask wrapper around the service layer
- **CLI**: `cli.py` — terminal interface using the same service layer
- **Agent hierarchy**: BaseAgent → ReasoningAgent → ResearchAgent → MultiLanguageResearchAgent
- **LLM providers**: OpenAI, Anthropic, DeepSeek with automatic fallback chains and streaming
- **Web search**: Tavily API with exact-match + semantic vector cache (sqlite-vec)
- **BYOK**: Users can provide their own API keys via Settings page (session-based, never stored in DB)
- **Storage**: SQLite for research history, search cache, and translation cache
- **All agent operations are async** (asyncio), run in background threads from Flask

## API Keys

| Service | Required | Purpose |
|---------|----------|---------|
| Tavily | Yes | Web search |
| OpenAI / DeepSeek / Anthropic | At least one | LLM reasoning & streaming |
| Google Translate | No | Optional translation provider |

Users can also bring their own keys (BYOK) via the `/settings` page.
