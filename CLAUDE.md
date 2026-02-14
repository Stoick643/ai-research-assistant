# AI Research Assistant

An AI-powered research assistant that conducts web searches, synthesizes findings using LLMs, and generates comprehensive multi-language reports.

## Project Structure

```
├── app.py                          # Flask web app (main entrypoint)
├── src/
│   ├── agents/                     # Agent implementations
│   │   ├── base.py                 # Base agent class
│   │   ├── reasoning.py            # Step-by-step reasoning agent
│   │   ├── reactive.py             # Event-driven agent with tools
│   │   ├── research_agent.py       # Web research agent
│   │   └── multilang_research_agent.py  # Multi-language research
│   ├── tools/                      # Tool integrations
│   │   ├── web_search.py           # Tavily web search
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
│       ├── rate_limiting.py        # Rate limiting, fallback chains, request queuing
│       ├── config.py               # Configuration management
│       └── logger.py               # Structured logging
├── examples/                       # Example agent scripts
├── tests/                          # Test suite (pytest)
├── docs/                           # Additional documentation
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
# Development server
python app.py

# Production
gunicorn app:app --bind 0.0.0.0:5003 --workers 2 --timeout 120
```

## Key Commands

```bash
pytest                              # Run tests
pytest --cov=src                    # Tests with coverage
black . && isort .                  # Format code
mypy src/                           # Type checking
```

## Architecture

- **Entrypoint**: `app.py` — Flask app with inline templates, background research via threads
- **Agent hierarchy**: BaseAgent → ReasoningAgent → ResearchAgent → MultiLanguageResearchAgent
- **LLM providers**: OpenAI, Anthropic, DeepSeek with automatic fallback chains (see `src/utils/rate_limiting.py`)
- **Web search**: Tavily API (`src/tools/web_search.py`)
- **Storage**: SQLite for research history and translation cache
- **All agent operations are async** (asyncio), run in background threads from Flask

## API Keys

| Service | Required | Purpose |
|---------|----------|---------|
| Tavily | Yes | Web search |
| OpenAI / DeepSeek / Anthropic | At least one | LLM reasoning |
| Google Translate | No | Optional translation |
