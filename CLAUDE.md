# Python AI Agents Project

This project provides a comprehensive framework for building autonomous AI agents in Python. It includes base classes, utilities, and examples for creating intelligent agents that can reason, react to events, and use tools.

## Project Structure

```
python-agents/
├── src/
│   ├── agents/          # Core agent implementations
│   │   ├── base.py      # Base agent class and common types
│   │   ├── reasoning.py # Reasoning agent implementation
│   │   └── reactive.py  # Reactive agent with tools and events
│   └── utils/           # Utility modules
│       ├── llm.py       # LLM client abstractions
│       ├── config.py    # Configuration management
│       └── logger.py    # Structured logging setup
├── examples/            # Example agent implementations
├── tests/              # Test suite
├── config/             # Configuration files
└── pyproject.toml      # Project dependencies and metadata
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Install the project in development mode
pip install -e ".[dev]"

# Or install just the runtime dependencies
pip install -e .
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Use either OpenAI or Anthropic
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4

# OR

ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-sonnet-20240229
```

### 3. Available Commands

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Format code
black .

# Sort imports
isort .

# Type checking
mypy src/

# Lint code
flake8 src/
```

## Agent Types

### BaseAgent
The foundation class that all agents inherit from. Provides:
- Message handling and state management
- Goal planning and task execution
- Context management
- Structured logging

### ReasoningAgent
An agent that uses step-by-step reasoning to solve problems:
- Breaks down complex goals into actionable tasks
- Uses LLM for reasoning and problem-solving
- Maintains conversation history and context

### ReactiveAgent
An event-driven agent that can use tools:
- Registers and uses external tools
- Responds to events and triggers
- Supports asynchronous event handling
- Tool execution with error handling

## Usage Examples

### Simple Chat Agent

```python
import asyncio
from src.agents import ReasoningAgent
from src.utils import create_llm_client

async def main():
    llm_client = create_llm_client("openai", api_key="your-key")
    agent = ReasoningAgent("ChatBot", llm_client)
    
    response = await agent.process_message("Explain quantum computing")
    print(response.content)

asyncio.run(main())
```

### Tool-Using Agent

```python
from src.agents import ReactiveAgent

async def file_tool(args: str) -> str:
    # Tool implementation
    return f"File operation result: {args}"

agent = ReactiveAgent("TaskAgent", llm_client)
agent.register_tool("file", file_tool)

# Agent can now use the file tool when processing messages
result = await agent.run("Read and summarize the README file")
```

## Configuration

The project uses Pydantic for configuration management. Key configuration options:

- **LLM Settings**: Provider, model, API keys, temperature
- **Agent Settings**: Max iterations, timeout, memory size
- **Optional Services**: Redis for caching, database for persistence

Configuration can be loaded from environment variables or dictionary:

```python
from src.utils import Config

# From environment
config = Config.from_env()

# From dictionary
config = Config.from_dict({
    "llm": {"provider": "openai", "api_key": "key", "model": "gpt-4"}
})
```

## Testing

The project includes comprehensive tests using pytest:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

## Extending the Framework

### Creating Custom Agents

1. Inherit from `BaseAgent`
2. Implement required abstract methods:
   - `process_message()`: Handle incoming messages
   - `plan()`: Break down goals into tasks
   - `execute_task()`: Execute individual tasks

### Adding Tools

Tools are async functions that agents can call:

```python
async def my_tool(args: str) -> str:
    # Tool implementation
    return "tool result"

agent.register_tool("my_tool", my_tool)
```

### Event Handling

Register event handlers for reactive behavior:

```python
async def on_task_complete(data):
    print(f"Task completed: {data}")

agent.register_event_handler("task_completed", on_task_complete)
```

## Architecture Notes

- **Async/Await**: All agent operations are asynchronous
- **Type Hints**: Full type annotations for better IDE support
- **Pydantic Models**: Structured data validation and serialization
- **Structured Logging**: JSON-formatted logs with context
- **Error Handling**: Comprehensive error handling and retries
- **Modular Design**: Easy to extend and customize

## Dependencies

Key dependencies include:
- `openai` / `anthropic`: LLM API clients
- `pydantic`: Data validation and settings
- `structlog`: Structured logging
- `tenacity`: Retry logic
- `asyncio`: Asynchronous operations
- `pytest`: Testing framework

## Development Workflow

1. Make changes to the codebase
2. Run tests: `pytest`
3. Format code: `black . && isort .`
4. Type check: `mypy src/`
5. Run linting: `flake8 src/`

The project is configured with pre-commit hooks for automatic code formatting and validation.

## Future Enhancements

- Memory persistence with databases
- Multi-agent coordination and communication
- Plugin system for extending functionality
- Web interface for agent management
- Integration with external APIs and services