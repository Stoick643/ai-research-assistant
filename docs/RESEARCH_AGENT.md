# Research Agent Usage Guide

The Research Agent is an AI-powered research assistant that conducts comprehensive web research and generates structured reports. This guide covers how to use the Research Agent effectively.

## Quick Start

### 1. Environment Setup

Ensure you have the required API keys configured:

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your API keys
TAVILY_API_KEY=your_tavily_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
# OR
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 2. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 3. Run the CLI Research Assistant

```bash
python examples/research_assistant.py
```

## Features

### Comprehensive Research Pipeline

The Research Agent follows a structured 5-phase research process:

1. **Query Generation**: Creates targeted search queries based on your topic
2. **Web Search**: Executes searches using Tavily API for AI-optimized results
3. **Source Analysis**: Uses LLM to analyze and synthesize information
4. **Report Generation**: Creates structured markdown reports
5. **Report Saving**: Saves timestamped reports with metadata

### Key Capabilities

- **Multi-Query Research**: Generates and executes multiple targeted search queries
- **Source Synthesis**: Combines information from multiple sources into coherent analysis
- **Structured Reports**: Generates professional markdown reports with consistent formatting
- **Focus Areas**: Support for specifying particular aspects to emphasize
- **Progress Tracking**: Real-time progress indicators during research execution
- **Error Recovery**: Robust error handling for failed searches or API issues

## Usage Examples

### Basic Research

```python
import asyncio
from src.agents import ResearchAgent
from src.utils import create_llm_client

async def basic_research():
    # Initialize LLM client
    llm_client = create_llm_client("openai", api_key="your-key")
    
    # Create research agent
    agent = ResearchAgent("ResearchBot", llm_client)
    
    # Conduct research
    result = await agent.conduct_research("Climate change impacts 2024")
    
    print(f"Report saved to: {result['report_path']}")
    print(f"Processed {result['total_queries']} queries")
    print(f"Found {result['total_sources']} sources")

asyncio.run(basic_research())
```

### Research with Focus Areas

```python
async def focused_research():
    agent = ResearchAgent("ResearchBot", llm_client)
    
    # Research with specific focus areas
    result = await agent.conduct_research(
        topic="Artificial Intelligence in Healthcare",
        focus_areas=["medical diagnosis", "drug discovery", "patient care"]
    )
    
    return result
```

### Custom Configuration

```python
from src.tools import WebSearchTool, MarkdownWriter

async def custom_research():
    # Custom web search configuration
    web_search = WebSearchTool(api_key="your-tavily-key")
    
    # Custom report writer (different output directory)
    report_writer = MarkdownWriter(output_dir="custom_reports")
    
    # Create agent with custom tools
    agent = ResearchAgent(
        name="CustomResearcher",
        llm_client=llm_client,
        web_search_tool=web_search,
        report_writer=report_writer,
        max_search_queries=7  # More comprehensive search
    )
    
    result = await agent.conduct_research("Quantum Computing Applications")
    return result
```

## CLI Interface

The command-line interface provides an interactive way to conduct research:

### Starting the CLI

```bash
python examples/research_assistant.py
```

### CLI Features

- **Interactive Prompts**: Guided input for research topics and focus areas
- **Progress Indicators**: Real-time progress bars and status updates
- **Results Summary**: Detailed summary of research metrics
- **Continuous Operation**: Option to conduct multiple research sessions
- **Error Handling**: User-friendly error messages and recovery options

### Example CLI Session

```
🔍 AI Research Assistant

Welcome to the AI Research Assistant!

Enter your research topic: AI trends 2025
Optional: Enter specific focus areas (comma-separated): business applications, safety

Research Plan:
📋 Topic: AI trends 2025
🎯 Focus Areas: business applications, safety

🔍 Searching web... ████████████████████ 100%
🧠 Analyzing sources... ████████████████████ 100%
📝 Generating report... ████████████████████ 100%

Research Results Summary
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric             ┃ Value                                            ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Topic              │ AI trends 2025                                   │
│ Queries Executed   │ 5                                                │
│ Sources Found      │ 23                                               │
│ Processing Time    │ 1m 23s                                          │
│ Report Path        │ reports/research_report_ai_trends_2025_...md    │
└────────────────────┴──────────────────────────────────────────────────┘

✅ Research completed successfully!
📄 Report saved to: reports/research_report_ai_trends_2025_20241230_143022.md
```

## Report Structure

### Standard Report Format

Generated reports follow a consistent structure:

```markdown
# Research Report: [Topic]

## Executive Summary
[2-3 paragraph overview of key insights]

## Key Findings
- **Finding 1**: [Concise description]
- **Finding 2**: [Concise description]
- **Finding 3**: [Concise description]

## Detailed Analysis
[Comprehensive analysis organized by themes]

## Sources
1. [Source Title](URL)
2. [Source Title](URL)
...

## Metadata
- **Research Date**: YYYY-MM-DD HH:MM:SS
- **Query Count**: N
- **Processing Time**: Xs or XmYs
```

### Report Customization

You can extend the report format by subclassing `ReportFormatter`:

```python
from src.tools.report_writer import ReportFormatter

class CustomReportFormatter(ReportFormatter):
    @staticmethod
    def format_research_report(topic, executive_summary, key_findings, 
                             detailed_analysis, sources, query_count, processing_time):
        # Add custom sections or formatting
        report = ReportFormatter.format_research_report(
            topic, executive_summary, key_findings, 
            detailed_analysis, sources, query_count, processing_time
        )
        
        # Add custom footer
        report += "\n\n## Custom Analysis\n[Your custom content here]"
        return report
```

## Best Practices

### Effective Topic Formulation

**Good Topics:**
- "Machine Learning in Financial Risk Assessment 2024"
- "Sustainable Energy Technologies: Solar and Wind Power Advances"
- "Cybersecurity Threats in Remote Work Environments"

**Less Effective Topics:**
- "Technology" (too broad)
- "AI" (too general)
- "How to code" (not research-oriented)

### Using Focus Areas

Focus areas help narrow research scope and improve relevance:

```python
# Broad topic with specific focus
topic = "Climate Change"
focus_areas = ["renewable energy", "policy changes", "economic impact"]

# Technology topic with application focus
topic = "Blockchain Technology"
focus_areas = ["supply chain", "healthcare", "finance"]
```

### Managing Research Scope

- **Max Queries**: Adjust `max_search_queries` based on topic complexity
  - Simple topics: 3-5 queries
  - Complex topics: 5-8 queries
  - Comprehensive research: 8-12 queries

- **Search Depth**: Configure search depth in WebSearchTool
  - "basic": Faster, good for general topics
  - "advanced": Slower, better for specialized topics

## Integration with Other Agents

### Using Research Results in Other Agents

```python
# Conduct research first
research_result = await research_agent.conduct_research("AI Ethics")

# Use results in another agent
reasoning_agent = ReasoningAgent("Analyst", llm_client)
analysis = await reasoning_agent.process_message(
    f"Based on this research: {research_result['analysis']}, "
    f"what are the key ethical considerations for AI development?"
)
```

### Chaining Research Tasks

```python
async def multi_stage_research():
    # Stage 1: Broad research
    broad_result = await agent.conduct_research("Renewable Energy")
    
    # Stage 2: Focused follow-up based on findings
    key_finding = broad_result['analysis'][:500]  # First key finding
    
    detailed_result = await agent.conduct_research(
        "Solar Panel Efficiency Improvements",
        focus_areas=["materials", "manufacturing", "cost reduction"]
    )
    
    return broad_result, detailed_result
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

## API Reference

### ResearchAgent Class

```python
class ResearchAgent(ReasoningAgent):
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        web_search_tool: Optional[WebSearchTool] = None,
        report_writer: Optional[ReportWriter] = None,
        description: str = "...",
        max_search_queries: int = 5,
        **kwargs
    )
    
    async def conduct_research(
        self, 
        topic: str, 
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]
    
    async def analyze_sources(
        self, 
        topic: str, 
        search_responses: List[SearchResponse]
    ) -> str
    
    async def generate_report(
        self, 
        topic: str, 
        analysis: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str
```

### Key Methods

- `conduct_research()`: Main research pipeline
- `analyze_sources()`: LLM-powered source analysis
- `generate_report()`: Structured report creation

### Return Values

The `conduct_research()` method returns a dictionary with:

```python
{
    "topic": str,              # Research topic
    "report_path": str,        # Path to saved report
    "report_content": str,     # Full report content
    "total_queries": int,      # Number of search queries
    "total_sources": int,      # Number of sources found
    "processing_time": float,  # Time in seconds
    "analysis": str,           # Source analysis
    "search_queries": List[str] # Generated queries
}
```