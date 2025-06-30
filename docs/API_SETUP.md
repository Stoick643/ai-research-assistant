# API Setup Guide

This guide covers how to set up the required API keys and services for the Research Agent system.

## Required APIs

### 1. Tavily API (Required)

Tavily provides AI-optimized web search specifically designed for AI applications.

#### Getting a Tavily API Key

1. **Sign up** at [https://tavily.com](https://tavily.com)
2. **Create an account** or log in
3. **Navigate to API section** in your dashboard
4. **Generate an API key**
5. **Copy the API key** (starts with `tvly-`)

#### Tavily Pricing

- **Free Tier**: 1,000 requests/month
- **Starter**: $20/month for 10,000 requests
- **Professional**: $100/month for 100,000 requests
- **Enterprise**: Custom pricing

#### Tavily Features Used

- **Search API**: Core web search functionality
- **Answer Generation**: AI-generated answers from search results
- **Content Extraction**: Clean, AI-ready content from web pages
- **Context Retrieval**: Optimized content for RAG applications

### 2. LLM API (Required - Choose One)

#### Option A: OpenAI API

**Getting an OpenAI API Key:**
1. Visit [https://platform.openai.com](https://platform.openai.com)
2. Create an account or log in
3. Go to API Keys section
4. Create a new API key
5. Copy the key (starts with `sk-`)

**Supported Models:**
- `gpt-4` (recommended for research)
- `gpt-4-turbo`
- `gpt-3.5-turbo` (cost-effective option)

**Pricing (as of 2024):**
- GPT-4: $30/1M input tokens, $60/1M output tokens
- GPT-3.5-turbo: $1/1M input tokens, $2/1M output tokens

#### Option B: Anthropic API (Claude)

**Getting an Anthropic API Key:**
1. Visit [https://console.anthropic.com](https://console.anthropic.com)
2. Create an account or log in
3. Go to API Keys section
4. Create a new API key
5. Copy the key

**Supported Models:**
- `claude-3-sonnet-20240229` (recommended)
- `claude-3-haiku-20240307` (faster, cost-effective)
- `claude-3-opus-20240229` (highest capability)

**Pricing (as of 2024):**
- Claude 3 Sonnet: $3/1M input tokens, $15/1M output tokens
- Claude 3 Haiku: $0.25/1M input tokens, $1.25/1M output tokens

## Environment Configuration

### 1. Create Environment File

```bash
# Copy the example environment file
cp .env.example .env
```

### 2. Configure API Keys

Edit the `.env` file with your API keys:

```env
# Tavily API (Required)
TAVILY_API_KEY=tvly-your_tavily_api_key_here

# LLM API (Choose one)
# Option 1: OpenAI
OPENAI_API_KEY=sk-your_openai_api_key_here
OPENAI_MODEL=gpt-4

# Option 2: Anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Optional LLM Configuration
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.3

# Optional Agent Configuration
AGENT_MAX_ITERATIONS=10
AGENT_TIMEOUT=300

# Optional Services
REDIS_URL=redis://localhost:6379
DATABASE_URL=sqlite:///agents.db
LOG_LEVEL=INFO
```

### 3. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TAVILY_API_KEY` | Yes | - | Tavily API key for web search |
| `OPENAI_API_KEY` | One of LLM | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | One of LLM | - | Anthropic API key |
| `OPENAI_MODEL` | No | `gpt-4` | OpenAI model to use |
| `ANTHROPIC_MODEL` | No | `claude-3-sonnet-20240229` | Anthropic model to use |
| `LLM_MAX_TOKENS` | No | `1000` | Maximum tokens for LLM responses |
| `LLM_TEMPERATURE` | No | `0.7` | Temperature for LLM generation |
| `AGENT_MAX_ITERATIONS` | No | `10` | Max iterations for agent tasks |
| `AGENT_TIMEOUT` | No | `300` | Timeout in seconds |
| `LOG_LEVEL` | No | `INFO` | Logging level |

## Security Best Practices

### 1. API Key Security

**DO:**
- Store API keys in environment variables
- Use `.env` files for local development
- Add `.env` to `.gitignore`
- Use separate keys for development/production
- Rotate keys regularly

**DON'T:**
- Commit API keys to version control
- Share API keys in plain text
- Use production keys for development
- Hardcode keys in source code

### 2. Environment File Protection

```bash
# Secure the .env file
chmod 600 .env

# Ensure .env is in .gitignore
echo ".env" >> .gitignore
```

### 3. Production Deployment

For production environments, use:

- **Environment variables** in your deployment platform
- **Secret management services** (AWS Secrets Manager, Azure Key Vault, etc.)
- **Container secrets** (Docker secrets, Kubernetes secrets)
- **CI/CD secret storage** (GitHub Secrets, GitLab CI Variables)

## API Usage and Monitoring

### 1. Rate Limiting

**Tavily API:**
- Rate limits vary by plan
- Monitor usage in Tavily dashboard
- Implement exponential backoff (already included)

**OpenAI API:**
- Rate limits by model and tier
- Monitor in OpenAI dashboard
- Implement request queuing for high volume

**Anthropic API:**
- Rate limits by model
- Monitor in Anthropic console
- Built-in retry logic included

### 2. Usage Monitoring

```python
# Example: Monitor API usage
import os
from src.utils import Config

config = Config.from_env()
print(f"Using LLM provider: {config.llm.provider}")
print(f"Model: {config.llm.model}")
print(f"Max tokens: {config.llm.max_tokens}")
```

### 3. Cost Optimization

**Research Agent Typical Usage:**
- 1 research session: 5-10 API calls
- Token usage: 3,000-8,000 tokens per session
- Estimated cost: $0.05-$0.25 per research (GPT-4)

**Cost Reduction Tips:**
- Use GPT-3.5-turbo for development
- Implement result caching
- Optimize prompt lengths
- Use appropriate max_tokens settings

## Testing API Setup

### 1. Quick Test Script

```python
#!/usr/bin/env python3
"""Test API configuration."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_apis():
    """Test API connectivity."""
    
    # Test Tavily API
    try:
        from src.tools import WebSearchTool
        search_tool = WebSearchTool()
        result = await search_tool.qna_search("What is AI?")
        print("✅ Tavily API: Working")
    except Exception as e:
        print(f"❌ Tavily API: {e}")
    
    # Test LLM API
    try:
        from src.utils import create_llm_client
        
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        provider = "openai" if os.getenv("OPENAI_API_KEY") else "anthropic"
        
        client = create_llm_client(provider, api_key=api_key)
        response = await client.generate("You are helpful.", "Say hello.")
        print(f"✅ {provider.title()} API: Working")
    except Exception as e:
        print(f"❌ LLM API: {e}")

if __name__ == "__main__":
    asyncio.run(test_apis())
```

### 2. Run the Test

```bash
python test_apis.py
```

Expected output:
```
✅ Tavily API: Working
✅ OpenAI API: Working
```

## Troubleshooting

### Common Issues

#### "Tavily API key not found"
- Check `.env` file exists
- Verify `TAVILY_API_KEY` is set
- Ensure no extra spaces around the key
- Check file permissions on `.env`

#### "Invalid API key" errors
- Verify API key is correct
- Check for typos or extra characters
- Ensure key hasn't expired
- Test key in API provider's dashboard

#### "Rate limit exceeded"
- Wait for rate limit reset
- Implement request delays
- Upgrade API plan if needed
- Use exponential backoff

#### "Model not found"
- Check model name spelling
- Verify model is available in your region
- Update to supported model names
- Check API provider documentation

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
export LOG_LEVEL=DEBUG
python examples/research_assistant.py
```

### API Status Pages

Monitor API status:
- **Tavily**: Check their status page or dashboard
- **OpenAI**: [status.openai.com](https://status.openai.com)
- **Anthropic**: [status.anthropic.com](https://status.anthropic.com)

## Advanced Configuration

### Custom API Endpoints

```env
# Use custom OpenAI-compatible endpoint
LLM_BASE_URL=https://your-custom-endpoint.com/v1
OPENAI_API_KEY=your_custom_key
```

### Proxy Configuration

```env
# HTTP proxy settings
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=https://proxy.company.com:8080
```

### Multiple Environments

Use different `.env` files for different environments:

```bash
# Development
cp .env.example .env.dev

# Production  
cp .env.example .env.prod

# Load specific environment
python -c "from dotenv import load_dotenv; load_dotenv('.env.dev')"
```