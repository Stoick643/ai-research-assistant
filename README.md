# AI Research Assistant

**Live at: [airesearchassistant.fly.dev](https://airesearchassistant.fly.dev/)**

An AI-powered research assistant that conducts web searches, synthesizes findings using LLMs, and generates comprehensive multi-language reports.

## Features

- **Web Research**: Automated web search via Tavily API with source analysis
- **Multi-LLM Support**: OpenAI, Anthropic, and DeepSeek with automatic fallback chains
- **Streaming**: LLM responses stream into live preview during research
- **Multi-Language Reports**: Research in English, translated to 12+ languages
- **Semantic Cache**: sqlite-vec powered vector search — similar queries hit cache automatically
- **BYOK**: Bring your own API keys via Settings page (never stored in database)
- **CLI**: Full command-line interface alongside the web UI
- **Rate Limiting**: Built-in rate limiting, request queuing, and graceful degradation
- **Research History**: SQLite-backed research tracking and analytics

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
# Web UI
python app.py

# CLI
python cli.py "quantum computing trends 2025"
python cli.py "AI safety" --depth advanced --lang sl --output report.md
```

## CLI Usage

```bash
python cli.py "research topic"              # Basic research
python cli.py "topic" --depth advanced      # Thorough search (2x credits)
python cli.py "topic" --lang sl             # Translate to Slovenian
python cli.py "topic" --focus "area1,area2" # Focus on specific areas
python cli.py "topic" --output report.md    # Save to file
python cli.py "topic" --no-cache            # Skip cache, force fresh
```

## Project Structure

```
├── app.py                          # Flask web app (thin HTTP layer)
├── cli.py                          # CLI interface
├── src/
│   ├── services/                   # Business logic layer
│   │   └── research_service.py     # Core research orchestration
│   ├── agents/                     # Agent implementations
│   │   ├── research_agent.py       # Web research agent (streaming)
│   │   └── multilang_research_agent.py  # Multi-language research
│   ├── tools/                      # Tool integrations
│   │   ├── web_search.py           # Tavily web search
│   │   ├── search_cache.py         # Exact + semantic search cache
│   │   ├── embeddings.py           # Embedding providers (hash, OpenAI)
│   │   ├── report_writer.py        # Markdown report generation
│   │   └── translation.py          # Translation framework
│   ├── database/                   # Data persistence
│   │   ├── models.py               # SQLAlchemy models
│   │   └── sqlite_writer.py        # Research history writer
│   └── utils/                      # Utilities
│       ├── llm.py                  # LLM clients (OpenAI, Anthropic)
│       └── rate_limiting.py        # Rate limiting, fallback chains, streaming
├── templates/                      # Flask HTML templates
├── tests/                          # 156 tests (pytest)
└── docs/                           # Documentation & roadmap
```

## API Keys

| Service | Required | Purpose |
|---------|----------|---------|
| Tavily | Yes | Web search |
| OpenAI / DeepSeek / Anthropic | At least one | LLM reasoning & streaming |
| Google Translate | No | Optional translation provider |

Users can also bring their own keys via the `/settings` page (BYOK).

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black . && isort .
```

## Deployment

Deployed on Fly.io with GitHub Actions CI/CD.
See [docs/ROADMAP.md](docs/ROADMAP.md) for full development history.
