# Troubleshooting Guide

This guide covers common issues and solutions when using the Research Agent system.

## Quick Diagnosis

### Check System Status

```bash
# 1. Verify environment setup
python -c "import os; print('Tavily:', 'TAVILY_API_KEY' in os.environ); print('LLM:', bool(os.getenv('OPENAI_API_KEY') or os.getenv('ANTHROPIC_API_KEY')))"

# 2. Test dependencies
python -c "import tavily, openai, anthropic; print('Dependencies OK')"

# 3. Run test script
python -c "
import asyncio
from src.tools import WebSearchTool
async def test(): 
    try: 
        tool = WebSearchTool()
        result = await tool.qna_search('test')
        print('API Test: OK')
    except Exception as e: 
        print(f'API Test: {e}')
asyncio.run(test())
"
```

## Installation Issues

### "ModuleNotFoundError: No module named 'tavily'"

**Cause**: Missing dependencies

**Solution**:
```bash
# Install missing dependencies
pip install tavily-python

# Or reinstall all dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import tavily; print('Tavily installed')"
```

### "ImportError: No module named 'src'"

**Cause**: Python path issues

**Solution**:
```bash
# Install in development mode
pip install -e .

# Or add to Python path temporarily
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run from project root
cd /path/to/python-agents
python examples/research_assistant.py
```

### Package Version Conflicts

**Cause**: Incompatible dependency versions

**Solution**:
```bash
# Create fresh virtual environment
python -m venv fresh_env
source fresh_env/bin/activate  # Linux/Mac
# fresh_env\Scripts\activate  # Windows

# Install fresh dependencies
pip install -e ".[dev]"

# Check for conflicts
pip check
```

## API Configuration Issues

### "Tavily API key not found"

**Symptoms**: `ValueError: Tavily API key not found. Set TAVILY_API_KEY environment variable`

**Diagnosis**:
```bash
# Check if .env file exists
ls -la .env

# Check if key is set
grep TAVILY_API_KEY .env

# Check if environment variable is loaded
python -c "import os; print(os.getenv('TAVILY_API_KEY', 'NOT_SET'))"
```

**Solutions**:

1. **Create .env file**:
   ```bash
   cp .env.example .env
   # Edit .env with your API key
   ```

2. **Fix .env file format**:
   ```env
   # Correct format (no spaces around =)
   TAVILY_API_KEY=tvly-your-key-here
   
   # Incorrect formats:
   # TAVILY_API_KEY = tvly-your-key-here  (spaces)
   # TAVILY_API_KEY="tvly-your-key-here"  (quotes unnecessary)
   ```

3. **Set environment variable directly**:
   ```bash
   export TAVILY_API_KEY=tvly-your-key-here
   python examples/research_assistant.py
   ```

4. **Check file permissions**:
   ```bash
   chmod 644 .env
   ```

### "Either OPENAI_API_KEY or ANTHROPIC_API_KEY must be set"

**Cause**: No LLM API key configured

**Solution**:
```bash
# Option 1: OpenAI
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

# Option 2: Anthropic
echo "ANTHROPIC_API_KEY=your-key-here" >> .env

# Verify
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('OpenAI:', bool(os.getenv('OPENAI_API_KEY')))
print('Anthropic:', bool(os.getenv('ANTHROPIC_API_KEY')))
"
```

### "Invalid API key" or Authentication Errors

**Diagnosis**:
```bash
# Test Tavily key manually
curl -H "Content-Type: application/json" \
     -d '{"api_key":"YOUR_KEY","query":"test","search_depth":"basic","max_results":1}' \
     https://api.tavily.com/search

# Test OpenAI key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_KEY"
```

**Solutions**:

1. **Verify API key format**:
   - Tavily: starts with `tvly-`
   - OpenAI: starts with `sk-`
   - Anthropic: check Anthropic documentation

2. **Check for typos**:
   ```bash
   # Print key length (should not reveal actual key)
   python -c "import os; print('Tavily key length:', len(os.getenv('TAVILY_API_KEY', '')))"
   ```

3. **Generate new API key**:
   - Visit API provider dashboard
   - Generate new key
   - Update .env file

4. **Check account status**:
   - Verify account is active
   - Check billing/credit status
   - Ensure API access is enabled

## Runtime Issues

### "Web search failed: API Error"

**Symptoms**: Research fails during web search phase

**Diagnosis**:
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python examples/research_assistant.py
```

**Common Causes & Solutions**:

1. **Rate Limiting**:
   ```python
   # Add delays between requests
   import asyncio
   await asyncio.sleep(1)  # Wait 1 second between calls
   ```

2. **Network Issues**:
   ```bash
   # Test connectivity
   ping api.tavily.com
   curl -I https://api.tavily.com/
   ```

3. **Quota Exceeded**:
   - Check Tavily dashboard for usage
   - Upgrade plan if needed
   - Wait for quota reset

4. **Temporary API Issues**:
   - Check API status pages
   - Retry after a few minutes
   - Implement exponential backoff

### "LLM API call failed"

**Symptoms**: Research fails during analysis or report generation

**Diagnosis**:
```python
# Test LLM directly
import asyncio
from src.utils import create_llm_client

async def test_llm():
    client = create_llm_client("openai", api_key="your-key")
    response = await client.generate("You are helpful.", "Say hello.")
    print(response)

asyncio.run(test_llm())
```

**Solutions**:

1. **Check model availability**:
   ```python
   # List available models
   import openai
   client = openai.OpenAI(api_key="your-key")
   models = client.models.list()
   for model in models.data:
       print(model.id)
   ```

2. **Reduce token usage**:
   ```env
   # In .env file
   LLM_MAX_TOKENS=500
   ```

3. **Switch models**:
   ```env
   # Use more affordable model
   OPENAI_MODEL=gpt-3.5-turbo
   ```

### "Failed to save report"

**Symptoms**: Research completes but report saving fails

**Diagnosis**:
```python
# Check directory permissions
import os
from pathlib import Path

reports_dir = Path("reports")
print(f"Directory exists: {reports_dir.exists()}")
print(f"Is writable: {os.access(reports_dir, os.W_OK)}")
```

**Solutions**:

1. **Create reports directory**:
   ```bash
   mkdir -p reports
   chmod 755 reports
   ```

2. **Check disk space**:
   ```bash
   df -h .
   ```

3. **Fix permissions**:
   ```bash
   chmod 755 reports/
   chmod 644 reports/*.md
   ```

4. **Use custom directory**:
   ```python
   from src.tools import MarkdownWriter
   writer = MarkdownWriter(output_dir="/tmp/reports")
   ```

## Performance Issues

### Slow Research Performance

**Symptoms**: Research takes too long to complete

**Diagnosis**:
```python
# Enable timing logs
import time
start = time.time()
# ... run research ...
print(f"Total time: {time.time() - start:.1f}s")
```

**Solutions**:

1. **Reduce search queries**:
   ```python
   agent = ResearchAgent(
       name="FastResearcher",
       llm_client=llm_client,
       max_search_queries=3  # Reduce from default 5
   )
   ```

2. **Use faster models**:
   ```env
   # Switch to faster model
   OPENAI_MODEL=gpt-3.5-turbo
   # or
   ANTHROPIC_MODEL=claude-3-haiku-20240307
   ```

3. **Optimize search depth**:
   ```python
   # Use basic search instead of advanced
   search_tool = WebSearchTool()
   result = await search_tool.search(query, search_depth="basic")
   ```

4. **Implement caching**:
   ```python
   # Cache search results (custom implementation)
   import json
   
   cache_file = "search_cache.json"
   if os.path.exists(cache_file):
       with open(cache_file) as f:
           cached_results = json.load(f)
   ```

### Memory Issues

**Symptoms**: Process runs out of memory

**Solutions**:

1. **Limit concurrent operations**:
   ```python
   # Process searches sequentially instead of parallel
   for query in queries:
       result = await search_tool.search(query)
       results.append(result)
   ```

2. **Reduce content size**:
   ```python
   # Truncate long content
   content = result.content[:1000]  # Limit to 1000 chars
   ```

3. **Clear variables**:
   ```python
   # Explicitly clear large variables
   del large_search_results
   import gc
   gc.collect()
   ```

## CLI Issues

### "Rich module not found" or Display Issues

**Solution**:
```bash
# Install rich for CLI display
pip install rich

# Or update all dependencies
pip install -e ".[dev]"
```

### Keyboard Interrupt Handling

**Symptoms**: CLI doesn't handle Ctrl+C gracefully

**Solutions**:

1. **Force quit**:
   ```bash
   # Use Ctrl+C multiple times
   # Or force kill
   kill -9 $(pgrep -f research_assistant)
   ```

2. **Run with timeout**:
   ```bash
   timeout 300 python examples/research_assistant.py
   ```

### Terminal Encoding Issues

**Symptoms**: Special characters display incorrectly

**Solutions**:
```bash
# Set UTF-8 encoding
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Or run with encoding
python -X utf8 examples/research_assistant.py
```

## Testing Issues

### "pytest: command not found"

**Solution**:
```bash
# Install pytest
pip install pytest

# Or install dev dependencies
pip install -e ".[dev]"
```

### Test Failures

**Run specific tests**:
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_web_search.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html
```

**Common test issues**:

1. **Mock failures**:
   - Check test fixtures are correct
   - Verify mock data matches expected format

2. **Async test issues**:
   ```bash
   # Install pytest-asyncio
   pip install pytest-asyncio
   ```

3. **Import errors in tests**:
   ```bash
   # Run from project root
   cd /path/to/python-agents
   pytest
   ```

## Development Issues

### Code Formatting Errors

**Solutions**:
```bash
# Format code
black .
isort .

# Check formatting
black --check .
isort --check-only .

# Fix import order
isort --profile black .
```

### Type Checking Errors

**Solutions**:
```bash
# Run mypy
mypy src/

# Fix common issues
# - Add type hints
# - Import proper types
# - Use Optional[] for nullable values
```

### Pre-commit Hook Failures

**Solutions**:
```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files

# Skip hooks temporarily
git commit --no-verify
```

## Getting Help

### Debug Information Collection

When reporting issues, include:

1. **System info**:
   ```bash
   python --version
   pip list | grep -E "(tavily|openai|anthropic)"
   uname -a  # Linux/Mac
   ```

2. **Error messages**:
   ```bash
   # Full error output with stack trace
   python examples/research_assistant.py 2>&1 | tee error.log
   ```

3. **Configuration**:
   ```bash
   # Sanitized config (no API keys)
   python -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   print('Python path:', os.path.dirname(__file__))
   print('Has Tavily key:', bool(os.getenv('TAVILY_API_KEY')))
   print('Has OpenAI key:', bool(os.getenv('OPENAI_API_KEY')))
   print('Has Anthropic key:', bool(os.getenv('ANTHROPIC_API_KEY')))
   "
   ```

### Contact and Support

- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check existing docs for solutions
- **Community**: Share experiences and solutions

### Emergency Workarounds

1. **Skip web search**:
   ```python
   # Use QnA search only
   answer = await web_search_tool.qna_search(topic)
   ```

2. **Manual report creation**:
   ```python
   # Create report without full research pipeline
   from src.tools.report_writer import ReportFormatter
   report = ReportFormatter.format_research_report(
       topic="Manual Topic",
       executive_summary="Manual summary",
       key_findings=["Finding 1", "Finding 2"],
       detailed_analysis="Manual analysis",
       sources=[],
       query_count=0,
       processing_time=0
   )
   ```

3. **Fallback to basic agent**:
   ```python
   # Use ReasoningAgent instead of ResearchAgent
   from src.agents import ReasoningAgent
   agent = ReasoningAgent("BasicAgent", llm_client)
   response = await agent.process_message(f"Research: {topic}")
   ```