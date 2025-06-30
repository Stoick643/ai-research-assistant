#!/usr/bin/env python3
"""
Research History CLI

Command-line interface for viewing and analyzing research history from SQLite database.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List
import json

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn
import typer

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.database import SQLiteWriter, ResearchAnalytics, DatabaseManager

app = typer.Typer(help="Research History and Analytics CLI")
console = Console()


class HistoryCLI:
    """CLI interface for research history management."""
    
    def __init__(self, database_path: str = "research_history.db"):
        self.database_path = database_path
        self.sqlite_writer = SQLiteWriter(database_path)
        self.analytics = ResearchAnalytics(database_path)
        self.console = Console()
    
    def display_research_list(self, research_list: List[dict], title: str = "Research History"):
        """Display research list in a formatted table."""
        if not research_list:
            self.console.print(f"[yellow]No research sessions found.[/yellow]")
            return
        
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Topic", style="green", width=40)
        table.add_column("Status", style="blue", width=10)
        table.add_column("Started", style="yellow", width=16)
        table.add_column("Duration", style="red", width=10)
        table.add_column("Queries", style="white", width=8)
        table.add_column("Sources", style="white", width=8)
        
        for research in research_list:
            started = research.get("started_at", "")
            if started:
                try:
                    dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    started = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    started = started[:16]
            
            duration = research.get("processing_time", 0)
            if duration:
                if duration < 60:
                    duration_str = f"{duration:.1f}s"
                else:
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = "N/A"
            
            status = research.get("status", "unknown")
            status_color = "green" if status == "completed" else "red" if status == "failed" else "yellow"
            
            table.add_row(
                str(research.get("id", "")),
                research.get("topic", "")[:38] + ("..." if len(research.get("topic", "")) > 38 else ""),
                f"[{status_color}]{status}[/{status_color}]",
                started,
                duration_str,
                str(research.get("total_queries", 0)),
                str(research.get("total_sources", 0))
            )
        
        self.console.print(table)
    
    def display_research_details(self, research: dict):
        """Display detailed information about a research session."""
        if not research:
            self.console.print("[red]Research not found.[/red]")
            return
        
        # Basic info panel
        info_text = f"""
[bold]Topic:[/bold] {research.get('topic', 'N/A')}
[bold]Agent:[/bold] {research.get('agent_name', 'N/A')}
[bold]Status:[/bold] {research.get('status', 'N/A')}
[bold]Started:[/bold] {research.get('started_at', 'N/A')}
[bold]Completed:[/bold] {research.get('completed_at', 'N/A')}
[bold]Processing Time:[/bold] {research.get('processing_time', 0):.1f} seconds
[bold]Total Queries:[/bold] {research.get('total_queries', 0)}
[bold]Total Sources:[/bold] {research.get('total_sources', 0)}
        """
        
        if research.get('focus_areas'):
            info_text += f"\n[bold]Focus Areas:[/bold] {', '.join(research['focus_areas'])}"
        
        panel = Panel(info_text, title=f"Research Details (ID: {research.get('id')})", border_style="blue")
        self.console.print(panel)
        
        # Executive Summary
        if research.get('executive_summary'):
            summary_panel = Panel(
                research['executive_summary'],
                title="Executive Summary",
                border_style="green"
            )
            self.console.print(summary_panel)
        
        # Key Findings
        if research.get('key_findings'):
            findings_text = ""
            for i, finding in enumerate(research['key_findings'], 1):
                findings_text += f"{i}. {finding}\n"
            
            findings_panel = Panel(
                findings_text.strip(),
                title="Key Findings",
                border_style="yellow"
            )
            self.console.print(findings_panel)
    
    def display_analytics_summary(self, analytics: dict, title: str):
        """Display analytics data in formatted panels."""
        if "error" in analytics:
            self.console.print(f"[red]Error: {analytics['error']}[/red]")
            return
        
        # Create summary table
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="white", width=30)
        table.add_column("Value", style="green", width=20)
        
        # Add relevant metrics based on analytics type
        if "total_research_sessions" in analytics:
            table.add_row("Total Research Sessions", str(analytics.get("total_research_sessions", 0)))
            table.add_row("Successful Sessions", str(analytics.get("successful_sessions", 0)))
            table.add_row("Success Rate", f"{analytics.get('success_rate_percent', 0):.1f}%")
            table.add_row("Avg Processing Time", f"{analytics.get('average_processing_time_seconds', 0):.1f}s")
        
        if "total_sources" in analytics:
            table.add_row("Total Sources", str(analytics.get("total_sources", 0)))
            table.add_row("Sources Used", str(analytics.get("sources_used_in_analysis", 0)))
            table.add_row("Usage Rate", f"{analytics.get('usage_rate_percent', 0):.1f}%")
            table.add_row("Avg Content Length", f"{analytics.get('average_content_length', 0):.0f} chars")
        
        if "total_queries" in analytics:
            table.add_row("Total Queries", str(analytics.get("total_queries", 0)))
            table.add_row("Successful Queries", str(analytics.get("successful_queries", 0)))
            table.add_row("Query Success Rate", f"{analytics.get('success_rate_percent', 0):.1f}%")
            table.add_row("Avg Results per Query", f"{analytics.get('average_results_per_query', 0):.1f}")
        
        self.console.print(table)


# CLI Commands

@app.command()
def list_research(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of records to show"),
    offset: int = typer.Option(0, "--offset", "-o", help="Number of records to skip"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path")
):
    """List recent research sessions."""
    cli = HistoryCLI(database)
    
    with console.status("Loading research history..."):
        research_list = cli.sqlite_writer.get_research_history(limit=limit, offset=offset)
    
    cli.display_research_list(research_list, f"Research History (Showing {len(research_list)} records)")


@app.command()
def show_research(
    research_id: int = typer.Argument(..., help="Research ID to display"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path")
):
    """Show detailed information about a specific research session."""
    cli = HistoryCLI(database)
    
    with console.status("Loading research details..."):
        research = cli.sqlite_writer.get_research_with_details(research_id)
    
    if research:
        cli.display_research_details(research)
        
        # Show queries and sources
        if research.get("queries"):
            console.print("\n[bold cyan]Search Queries:[/bold cyan]")
            for query in research["queries"]:
                status_icon = "✅" if query.get("success") else "❌"
                console.print(f"{status_icon} {query.get('text', 'N/A')} ({query.get('results_count', 0)} results)")
    else:
        console.print(f"[red]Research ID {research_id} not found.[/red]")


@app.command()
def search_research(
    query: str = typer.Argument(..., help="Search term"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of results to show"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path")
):
    """Search research sessions by topic or content."""
    cli = HistoryCLI(database)
    
    with console.status(f"Searching for '{query}'..."):
        results = cli.sqlite_writer.search_research(query, limit=limit)
    
    cli.display_research_list(results, f"Search Results for '{query}'")


@app.command()
def trends(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path")
):
    """Show research trends and analytics."""
    cli = HistoryCLI(database)
    
    with console.status("Analyzing research trends..."):
        trends_data = cli.analytics.get_research_trends(days)
    
    cli.display_analytics_summary(trends_data, f"Research Trends ({days} days)")
    
    # Show top topics
    if "top_topics" in trends_data and trends_data["top_topics"]:
        console.print("\n[bold cyan]Most Researched Topics:[/bold cyan]")
        for i, topic_data in enumerate(trends_data["top_topics"][:5], 1):
            console.print(f"{i}. {topic_data['topic']} ({topic_data['frequency']} times)")


@app.command()
def sources(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path")
):
    """Analyze source patterns and quality."""
    cli = HistoryCLI(database)
    
    with console.status("Analyzing source patterns..."):
        source_data = cli.analytics.get_source_analytics(days)
    
    cli.display_analytics_summary(source_data, f"Source Analytics ({days} days)")
    
    # Show top domains
    if "top_domains" in source_data and source_data["top_domains"]:
        console.print("\n[bold cyan]Top Source Domains:[/bold cyan]")
        for i, domain_data in enumerate(source_data["top_domains"][:5], 1):
            console.print(f"{i}. {domain_data['domain']} ({domain_data['source_count']} sources, score: {domain_data['average_relevance_score']:.3f})")


@app.command()
def queries(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path")
):
    """Analyze query patterns and effectiveness."""
    cli = HistoryCLI(database)
    
    with console.status("Analyzing query patterns..."):
        query_data = cli.analytics.get_query_patterns(days)
    
    cli.display_analytics_summary(query_data, f"Query Analytics ({days} days)")
    
    # Show common terms
    if "common_query_terms" in query_data and query_data["common_query_terms"]:
        console.print("\n[bold cyan]Common Query Terms:[/bold cyan]")
        for i, term_data in enumerate(query_data["common_query_terms"][:10], 1):
            console.print(f"{i}. {term_data['term']} ({term_data['frequency']} times)")


@app.command()
def stats(
    database: str = typer.Option("research_history.db", "--db", help="Database file path")
):
    """Show database statistics."""
    cli = HistoryCLI(database)
    
    with console.status("Loading database statistics..."):
        stats_data = cli.sqlite_writer.get_database_stats()
    
    if "error" in stats_data:
        console.print(f"[red]Error: {stats_data['error']}[/red]")
        return
    
    table = Table(title="Database Statistics", show_header=True, header_style="bold green")
    table.add_column("Metric", style="white", width=25)
    table.add_column("Value", style="cyan", width=20)
    
    table.add_row("Total Research Sessions", str(stats_data.get("total_research_sessions", 0)))
    table.add_row("Completed Sessions", str(stats_data.get("completed_sessions", 0)))
    table.add_row("Total Queries", str(stats_data.get("total_queries", 0)))
    table.add_row("Total Sources", str(stats_data.get("total_sources", 0)))
    
    if stats_data.get("average_processing_time"):
        table.add_row("Avg Processing Time", f"{stats_data['average_processing_time']:.1f}s")
    
    table.add_row("Database Location", stats_data.get("database_url", "Unknown"))
    
    console.print(table)


@app.command()
def delete_research(
    research_id: int = typer.Argument(..., help="Research ID to delete"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Delete a research session and all associated data."""
    cli = HistoryCLI(database)
    
    if not confirm:
        # Show research details first
        research = cli.sqlite_writer.get_research_by_id(research_id)
        if not research:
            console.print(f"[red]Research ID {research_id} not found.[/red]")
            return
        
        console.print(f"[yellow]Research to delete:[/yellow]")
        console.print(f"ID: {research['id']}")
        console.print(f"Topic: {research['topic']}")
        console.print(f"Started: {research['started_at']}")
        
        confirm = typer.confirm("Are you sure you want to delete this research session?")
    
    if confirm:
        success = cli.sqlite_writer.delete_research(research_id)
        if success:
            console.print(f"[green]Research ID {research_id} deleted successfully.[/green]")
        else:
            console.print(f"[red]Failed to delete research ID {research_id}.[/red]")
    else:
        console.print("Delete cancelled.")


@app.command()
def cleanup(
    days: int = typer.Option(30, "--days", "-d", help="Delete data older than this many days"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Clean up old research data."""
    cli = HistoryCLI(database)
    
    if not confirm:
        confirm = typer.confirm(f"Delete all research data older than {days} days?")
    
    if confirm:
        with console.status("Cleaning up old data..."):
            deleted_count = cli.sqlite_writer.cleanup_old_data(days)
        
        console.print(f"[green]Cleaned up {deleted_count} old research sessions.[/green]")
    else:
        console.print("Cleanup cancelled.")


@app.command()
def export_research(
    research_id: int = typer.Argument(..., help="Research ID to export"),
    output_file: str = typer.Option("research_export.json", "--output", "-o", help="Output file path"),
    database: str = typer.Option("research_history.db", "--db", help="Database file path")
):
    """Export research data to JSON file."""
    cli = HistoryCLI(database)
    
    with console.status("Exporting research data..."):
        research = cli.sqlite_writer.get_research_with_details(research_id)
    
    if not research:
        console.print(f"[red]Research ID {research_id} not found.[/red]")
        return
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(research, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]Research exported to {output_file}[/green]")
    except Exception as e:
        console.print(f"[red]Export failed: {e}[/red]")


if __name__ == "__main__":
    app()