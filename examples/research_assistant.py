#!/usr/bin/env python3
"""
Research Assistant CLI Application

A command-line interface for conducting AI-powered research using the ResearchAgent.
"""

import asyncio
import os
import sys
import time
from typing import Optional
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt
from rich.text import Text
from rich.panel import Panel
from rich.table import Table

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.agents import ResearchAgent
from src.tools import WebSearchTool, MarkdownWriter
from src.utils import create_llm_client, setup_logging
from src.utils.llm import normalize_text

# Load environment variables
load_dotenv()
setup_logging()

console = Console()


class ResearchAssistantCLI:
    """Command-line interface for the Research Assistant."""
    
    def __init__(self):
        self.agent = None
        self.console = Console()
        
    async def initialize(self) -> bool:
        """Initialize the research agent with API credentials."""
        try:
            # Check for API keys
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            provider = "openai" if os.getenv("OPENAI_API_KEY") else "anthropic"
            
            if not api_key:
                self.console.print(
                    "[red]Error:[/red] No LLM API key found. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable.",
                    style="red"
                )
                return False
            
            # Tavily API key check removed - WebSearchTool has hardcoded fallback
            
            # Initialize components
            llm_client = create_llm_client(provider, api_key=api_key)
            web_search_tool = WebSearchTool()
            report_writer = MarkdownWriter()
            
            # Create research agent
            self.agent = ResearchAgent(
                name="ResearchAssistant",
                llm_client=llm_client,
                web_search_tool=web_search_tool,
                report_writer=report_writer,
                description="An AI research assistant that conducts comprehensive web research"
            )
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error initializing research agent:[/red] {str(e)}")
            return False
    
    def display_welcome(self):
        """Display welcome message and instructions."""
        welcome_text = Text("🔍 AI Research Assistant", style="bold blue")
        
        panel_content = """
Welcome to the AI Research Assistant!

This tool will help you conduct comprehensive research on any topic by:
• Generating targeted search queries
• Searching the web for relevant information
• Analyzing and synthesizing sources
• Creating structured markdown reports

Simply enter your research topic when prompted, and the assistant will handle the rest.
        """
        
        panel = Panel(
            panel_content,
            title=welcome_text,
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
    
    def get_research_topic(self) -> Optional[str]:
        """Get research topic from user input."""
        try:
            topic = Prompt.ask(
                "[bold cyan]Enter your research topic[/bold cyan]",
                default="",
                show_default=False
            )
            
            if not topic.strip():
                self.console.print("[yellow]No topic provided. Exiting.[/yellow]")
                return None
            
            # Normalize text to handle Unicode encoding issues
            normalized_topic = normalize_text(topic.strip())
            return normalized_topic
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Research cancelled by user.[/yellow]")
            return None
    
    def get_focus_areas(self) -> Optional[list]:
        """Get optional focus areas from user."""
        try:
            focus_input = Prompt.ask(
                "[dim]Optional: Enter specific focus areas (comma-separated)[/dim]",
                default="",
                show_default=False
            )
            
            if not focus_input.strip():
                return None
                
            focus_areas = [area.strip() for area in focus_input.split(',') if area.strip()]
            return focus_areas if focus_areas else None
            
        except KeyboardInterrupt:
            return None
    
    async def conduct_research_with_progress(self, topic: str, focus_areas: Optional[list] = None) -> Optional[dict]:
        """Conduct research with progress indicators."""
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            transient=True
        ) as progress:
            
            # Create progress tasks
            search_task = progress.add_task("🔍 Searching web...", total=100)
            analysis_task = progress.add_task("🧠 Analyzing sources...", total=100)
            report_task = progress.add_task("📝 Generating report...", total=100)
            
            try:
                # Start research
                start_time = time.time()
                
                # Phase 1: Web search
                progress.update(search_task, advance=20)
                await asyncio.sleep(0.1)  # Small delay for UI
                
                # Conduct the actual research
                result = await self.agent.conduct_research(topic, focus_areas)
                
                # Update progress as research completes
                progress.update(search_task, completed=100)
                progress.update(analysis_task, advance=50)
                
                await asyncio.sleep(0.1)
                progress.update(analysis_task, completed=100)
                progress.update(report_task, advance=75)
                
                await asyncio.sleep(0.1)
                progress.update(report_task, completed=100)
                
                return result
                
            except Exception as e:
                progress.stop()
                self.console.print(f"[red]Research failed:[/red] {str(e)}")
                return None
    
    def display_research_results(self, result: dict):
        """Display research results summary."""
        
        # Create results table
        table = Table(title="Research Results Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="green")
        
        # Add metrics
        processing_time = result.get('processing_time', 0)
        time_str = f"{processing_time:.1f}s" if processing_time < 60 else f"{int(processing_time//60)}m {int(processing_time%60)}s"
        
        table.add_row("Topic", result.get('topic', 'N/A'))
        table.add_row("Queries Executed", str(result.get('total_queries', 0)))
        table.add_row("Sources Found", str(result.get('total_sources', 0)))
        table.add_row("Processing Time", time_str)
        table.add_row("Report Path", result.get('report_path', 'N/A'))
        
        self.console.print()
        self.console.print(table)
        
        # Success message
        success_panel = Panel(
            f"✅ Research completed successfully!\n\n"
            f"📄 Report saved to: [bold cyan]{result.get('report_path', 'N/A')}[/bold cyan]\n\n"
            f"You can now view the comprehensive markdown report with all findings, analysis, and sources.",
            title="[bold green]Success[/bold green]",
            border_style="green"
        )
        
        self.console.print()
        self.console.print(success_panel)
    
    def ask_continue(self) -> bool:
        """Ask user if they want to conduct another research."""
        try:
            response = Prompt.ask(
                "\n[bold cyan]Would you like to conduct another research?[/bold cyan]",
                choices=["y", "n", "yes", "no"],
                default="n",
                show_choices=False
            )
            return response.lower() in ["y", "yes"]
        except KeyboardInterrupt:
            return False
    
    async def run(self):
        """Main CLI loop."""
        self.display_welcome()
        
        # Initialize the agent
        if not await self.initialize():
            return
        
        self.console.print("[green]✅ Research Assistant initialized successfully![/green]\n")
        
        while True:
            try:
                # Get research topic
                topic = self.get_research_topic()
                if not topic:
                    break
                
                # Get optional focus areas
                focus_areas = self.get_focus_areas()
                
                # Display research plan
                self.console.print(f"\n[bold]Research Plan:[/bold]")
                self.console.print(f"📋 Topic: [cyan]{topic}[/cyan]")
                if focus_areas:
                    self.console.print(f"🎯 Focus Areas: [dim]{', '.join(focus_areas)}[/dim]")
                self.console.print()
                
                # Conduct research
                result = await self.conduct_research_with_progress(topic, focus_areas)
                
                if result:
                    self.display_research_results(result)
                    
                    # Ask if user wants to continue
                    if not self.ask_continue():
                        break
                else:
                    self.console.print("[red]Research failed. Please try again.[/red]")
                    if not self.ask_continue():
                        break
                        
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Research interrupted by user.[/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Unexpected error:[/red] {str(e)}")
                break
        
        self.console.print("\n[dim]Thank you for using the AI Research Assistant! 👋[/dim]")


async def main():
    """Main entry point."""
    cli = ResearchAssistantCLI()
    await cli.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Application terminated by user.[/yellow]")
    except Exception as e:
        console.print(f"[red]Fatal error:[/red] {str(e)}")
        sys.exit(1)