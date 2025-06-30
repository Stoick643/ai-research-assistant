# SQLite Database Features

The Research Assistant Agent includes comprehensive SQLite database integration for tracking research history, analytics, and insights. This document covers all database-related features and usage.

## Overview

The SQLite integration provides:
- **Automatic Research Tracking**: Every research session is automatically stored
- **Comprehensive Analytics**: Trends, patterns, and insights from historical data  
- **CLI Management**: Command-line tools for viewing and analyzing research history
- **Data Export**: Export research data for external analysis
- **Performance Metrics**: Track query effectiveness and source quality

## Database Schema

### Core Tables

#### Research Table
Stores complete research sessions with metadata:

```sql
CREATE TABLE research (
    id INTEGER PRIMARY KEY,
    topic VARCHAR(500) NOT NULL,
    focus_areas JSON,
    agent_name VARCHAR(100) NOT NULL,
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    processing_time FLOAT,
    status VARCHAR(20) DEFAULT 'in_progress',
    executive_summary TEXT,
    key_findings JSON,
    detailed_analysis TEXT,
    report_content TEXT,
    report_path VARCHAR(500),
    total_queries INTEGER DEFAULT 0,
    total_sources INTEGER DEFAULT 0,
    error_message TEXT,
    research_metadata JSON
);
```

#### Query Table
Individual search queries within research sessions:

```sql
CREATE TABLE queries (
    id INTEGER PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    query_text VARCHAR(1000) NOT NULL,
    query_order INTEGER NOT NULL,
    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    max_results INTEGER DEFAULT 5,
    search_depth VARCHAR(20) DEFAULT 'basic',
    include_answer BOOLEAN DEFAULT 1,
    results_count INTEGER DEFAULT 0,
    ai_answer TEXT,
    follow_up_questions JSON,
    search_context TEXT,
    execution_time FLOAT,
    success BOOLEAN DEFAULT 1,
    error_message TEXT
);
```

#### Source Table
Individual sources/results from search queries:

```sql
CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    research_id INTEGER REFERENCES research(id),
    query_id INTEGER REFERENCES queries(id),
    title VARCHAR(1000) NOT NULL,
    url VARCHAR(2000) NOT NULL,
    content TEXT,
    relevance_score FLOAT,
    published_date VARCHAR(20),
    retrieved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    content_length INTEGER,
    domain VARCHAR(200),
    used_in_analysis BOOLEAN DEFAULT 0
);
```

## Usage Guide

### Automatic Tracking

Database tracking is enabled by default when using the ResearchAgent:

```python
from src.agents import ResearchAgent
from src.utils import create_llm_client

# Database tracking enabled automatically
llm_client = create_llm_client("openai", api_key="your-key")
agent = ResearchAgent("MyAgent", llm_client)

# Conduct research - automatically tracked in database
result = await agent.conduct_research("AI trends 2025")
print(f"Research ID: {result['research_id']}")
```

### Custom Database Configuration

```python
from src.database import SQLiteWriter
from src.agents import ResearchAgent

# Custom database path
sqlite_writer = SQLiteWriter(database_path="custom_research.db")

agent = ResearchAgent(
    name="CustomAgent",
    llm_client=llm_client,
    sqlite_writer=sqlite_writer,
    enable_database_tracking=True
)
```

### Disable Database Tracking

```python
agent = ResearchAgent(
    name="NoDBAgent",
    llm_client=llm_client,
    enable_database_tracking=False  # Disable tracking
)
```

## CLI Commands

### Research History Management

```bash
# List recent research sessions
python examples/research_history_cli.py list-research --limit 10

# Show detailed research information
python examples/research_history_cli.py show-research 123

# Search research by topic
python examples/research_history_cli.py search-research "AI trends"

# Export research to JSON
python examples/research_history_cli.py export-research 123 --output research.json
```

### Analytics and Insights

```bash
# View research trends (last 30 days)
python examples/research_history_cli.py trends --days 30

# Analyze source patterns and quality
python examples/research_history_cli.py sources --days 30

# Query pattern analysis
python examples/research_history_cli.py queries --days 30

# Database statistics
python examples/research_history_cli.py stats
```

### Data Management

```bash
# Delete specific research session
python examples/research_history_cli.py delete-research 123

# Clean up old data (older than 30 days)
python examples/research_history_cli.py cleanup --days 30

# Use custom database
python examples/research_history_cli.py stats --db custom_research.db
```

## Analytics Features

### Research Trends Analysis

Track research volume, success rates, and topic patterns:

```python
from src.database import ResearchAnalytics

analytics = ResearchAnalytics()
trends = analytics.get_research_trends(days=30)

print(f"Total research sessions: {trends['total_research_sessions']}")
print(f"Success rate: {trends['success_rate_percent']}%")
print(f"Top topics: {trends['top_topics']}")
```

### Source Quality Analysis

Analyze source effectiveness and domain patterns:

```python
source_analytics = analytics.get_source_analytics(days=30)

print(f"Total sources: {source_analytics['total_sources']}")
print(f"Usage rate: {source_analytics['usage_rate_percent']}%")
print(f"Top domains: {source_analytics['top_domains']}")
```

### Query Pattern Analysis

Understand search query effectiveness:

```python
query_patterns = analytics.get_query_patterns(days=30)

print(f"Query success rate: {query_patterns['success_rate_percent']}%")
print(f"Average results per query: {query_patterns['average_results_per_query']}")
print(f"Common terms: {query_patterns['common_query_terms']}")
```

### Comparative Analysis

Compare research patterns across topics:

```python
comparison = analytics.get_comparative_analysis(
    topic_keywords=["AI", "blockchain", "quantum computing"],
    days=90
)

for topic, metrics in comparison['comparisons'].items():
    print(f"{topic}: {metrics['research_count']} sessions, "
          f"{metrics['success_rate_percent']}% success rate")
```

## Direct Database Access

### Using SQLiteWriter

```python
from src.database import SQLiteWriter

writer = SQLiteWriter("research_history.db")

# Get research history
history = writer.get_research_history(limit=20)

# Search research
results = writer.search_research("artificial intelligence")

# Get detailed research with queries and sources
detailed = writer.get_research_with_details(research_id=123)

# Database statistics
stats = writer.get_database_stats()
```

### Using DatabaseManager

```python
from src.database import DatabaseManager

db_manager = DatabaseManager("research_history.db")
db_manager.initialize()

# Get database statistics
stats = db_manager.get_database_stats()

# Cleanup old data
deleted_count = db_manager.cleanup_old_data(days_old=30)

# Create backup
success = db_manager.backup_database("backup_research.db")
```

## Advanced Usage

### Custom Analytics Queries

Access the database directly for custom analysis:

```python
from src.database import DatabaseManager
from src.database.models import Research, Query, Source

db_manager = DatabaseManager()
db_manager.initialize()

with db_manager.get_session() as session:
    # Custom query: Research sessions by month
    from sqlalchemy import func, extract
    
    monthly_research = session.query(
        extract('year', Research.started_at).label('year'),
        extract('month', Research.started_at).label('month'),
        func.count(Research.id).label('count')
    ).group_by('year', 'month').all()
    
    for year, month, count in monthly_research:
        print(f"{int(year)}-{int(month):02d}: {count} research sessions")
```

### Batch Data Operations

```python
# Export all research data
with db_manager.get_session() as session:
    all_research = session.query(Research).all()
    research_data = [r.to_dict() for r in all_research]
    
    import json
    with open('all_research.json', 'w') as f:
        json.dump(research_data, f, indent=2, default=str)
```

### Performance Optimization

```python
# Use connection pooling for high-volume usage
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///research_history.db",
    poolclass=StaticPool,
    pool_pre_ping=True,
    pool_recycle=300
)
```

## Database Maintenance

### Regular Cleanup

Set up automated cleanup of old data:

```python
import schedule
import time
from src.database import DatabaseManager

def cleanup_old_research():
    db_manager = DatabaseManager()
    db_manager.initialize()
    deleted = db_manager.cleanup_old_data(days_old=90)
    print(f"Cleaned up {deleted} old research sessions")

# Run cleanup weekly
schedule.every().week.do(cleanup_old_research)

while True:
    schedule.run_pending()
    time.sleep(3600)  # Check every hour
```

### Database Backup

```python
from datetime import datetime
from src.database import DatabaseManager

db_manager = DatabaseManager()
db_manager.initialize()

# Create timestamped backup
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = f"research_backup_{timestamp}.db"

success = db_manager.backup_database(backup_path)
if success:
    print(f"Backup created: {backup_path}")
```

### Migration Support

```python
# Future schema migrations will be handled by:
db_manager = DatabaseManager()
success = db_manager.migrate_database()
```

## Configuration Options

### Environment Variables

```bash
# Custom database location
export DATABASE_URL="sqlite:///custom_path/research.db"

# Database logging level
export DB_LOG_LEVEL="DEBUG"
```

### Programmatic Configuration

```python
from src.utils import Config

config = Config.from_env()
config.database_url = "sqlite:///production_research.db"

# Use with ResearchAgent
agent = ResearchAgent(
    name="ProdAgent",
    llm_client=llm_client,
    sqlite_writer=SQLiteWriter(config.database_url.replace("sqlite:///", ""))
)
```

## Performance Considerations

### Database Size Management

- **Automatic cleanup**: Configure regular cleanup of old data
- **Selective retention**: Keep only high-value research sessions
- **Compression**: SQLite supports compression for large text fields

### Query Optimization

- **Indexed searches**: Key fields are automatically indexed
- **Pagination**: Use `limit` and `offset` for large result sets
- **Filtering**: Use date ranges and status filters for better performance

### Scaling Considerations

- **Single file limit**: SQLite handles databases up to 281 TB
- **Concurrent access**: SQLite supports multiple readers, single writer
- **Migration path**: Easy migration to PostgreSQL if needed

## Troubleshooting

### Common Issues

**Database locked errors:**
```python
# Ensure proper session cleanup
with db_manager.get_session() as session:
    # Do database operations
    pass  # Session automatically closed
```

**Performance issues:**
```python
# Enable WAL mode for better concurrency
import sqlite3
conn = sqlite3.connect("research_history.db")
conn.execute("PRAGMA journal_mode=WAL;")
conn.close()
```

**Disk space issues:**
```python
# Regular cleanup and vacuum
db_manager.cleanup_old_data(days_old=30)

# Manual vacuum (SQLite-specific)
with db_manager.get_session() as session:
    session.execute("VACUUM;")
```

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use structured logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
```

## Integration Examples

### With Existing Research Workflows

```python
# Integrate with existing research pipeline
async def enhanced_research_workflow(topic: str):
    agent = ResearchAgent("WorkflowAgent", llm_client)
    
    # Conduct research with automatic tracking
    result = await agent.conduct_research(topic)
    
    # Get analytics on similar past research
    analytics = ResearchAnalytics()
    similar_research = analytics.search_research(topic)
    
    # Compare with historical performance
    if similar_research:
        avg_time = sum(r['processing_time'] for r in similar_research) / len(similar_research)
        print(f"Current: {result['processing_time']:.1f}s, Average: {avg_time:.1f}s")
    
    return result
```

### Custom Report Generation

```python
# Generate custom analytics reports
def generate_monthly_report():
    analytics = ResearchAnalytics()
    
    # Get comprehensive analytics
    trends = analytics.get_research_trends(days=30)
    sources = analytics.get_source_analytics(days=30)
    queries = analytics.get_query_patterns(days=30)
    
    # Format as markdown report
    report = f"""
# Monthly Research Analytics Report

## Research Volume
- Total sessions: {trends['total_research_sessions']}
- Success rate: {trends['success_rate_percent']}%
- Average processing time: {trends['average_processing_time_seconds']}s

## Source Quality
- Total sources: {sources['total_sources']}
- Usage rate: {sources['usage_rate_percent']}%
- Top domains: {', '.join([d['domain'] for d in sources['top_domains'][:5]])}

## Query Effectiveness
- Success rate: {queries['success_rate_percent']}%
- Average results: {queries['average_results_per_query']}
- Common terms: {', '.join([t['term'] for t in queries['common_query_terms'][:10]])}
"""
    
    return report
```

The SQLite integration provides a powerful foundation for research analytics and historical insights, enabling continuous improvement of research effectiveness and quality.