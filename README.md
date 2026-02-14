# AI Research Assistant

An AI-powered research assistant that conducts web searches, synthesizes findings using LLMs, and generates comprehensive multi-language reports.

## Features

- **Web Research**: Automated web search via Tavily API with source analysis
- **Multi-LLM Support**: OpenAI, Anthropic, and DeepSeek with automatic fallback chains
- **Multi-Language Reports**: Research in English, translated to 12+ languages
- **Rate Limiting**: Built-in rate limiting and request queuing
- **Research History**: SQLite-backed research tracking and analytics
- **Flask Web UI**: Browser-based interface for submitting and viewing research

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys (at least one LLM provider + Tavily)
```

### 3. Run

```bash
# Development
python app.py

# Production
gunicorn app:app --bind 0.0.0.0:5003 --workers 2 --timeout 120
```

## Project Structure

```
├── app.py                          # Flask web application (main entrypoint)
├── src/
│   ├── agents/                     # Agent implementations
│   │   ├── base.py                 # Base agent class
│   │   ├── reasoning.py            # Step-by-step reasoning agent
│   │   ├── research_agent.py       # Web research agent
│   │   └── multilang_research_agent.py  # Multi-language research
│   ├── tools/                      # Tool integrations
│   │   ├── web_search.py           # Tavily web search
│   │   ├── report_writer.py        # Markdown report generation
│   │   ├── translation.py          # Translation framework
│   │   └── translation_cache.py    # Translation caching
│   ├── database/                   # Data persistence
│   │   ├── database.py             # Database setup
│   │   ├── models.py               # SQLAlchemy models
│   │   ├── sqlite_writer.py        # Research history writer
│   │   └── analytics.py            # Research analytics
│   └── utils/                      # Utilities
│       ├── llm.py                  # LLM client abstractions
│       ├── rate_limiting.py        # Rate limiting & fallback chains
│       ├── config.py               # Configuration management
│       └── logger.py               # Structured logging
├── examples/                       # Example scripts
├── tests/                          # Test suite
├── docs/                           # Documentation
├── .env.example                    # Environment variable template
├── Procfile                        # Production deployment (Render)
└── pyproject.toml                  # Project metadata & dependencies
```

## API Keys Required

| Service | Required | Purpose |
|---------|----------|---------|
| Tavily | Yes | Web search |
| OpenAI / DeepSeek / Anthropic | At least one | LLM reasoning & synthesis |
| Google Translate | No | Optional translation provider |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black . && isort .

# Type checking
mypy src/
```

## Deployment

The app is configured for deployment on Render (see `render.yaml` and `Procfile`).
See [DEPLOYMENT.md](DEPLOYMENT.md) for details.
