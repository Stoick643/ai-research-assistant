#!/usr/bin/env python3
"""
Multi-language Research Assistant CLI

Enhanced research assistant with translation capabilities and language selection.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.layout import Layout
from rich.live import Live
import typer

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.agents import MultiLanguageResearchAgent
from src.utils import create_llm_client
from src.utils.llm import normalize_text
from src.tools.translation import TranslationTool
from src.database import SQLiteWriter

app = typer.Typer(help="Multi-language Research Assistant CLI")
console = Console()


class MultiLangResearchCLI:
    """CLI interface for multi-language research assistant."""
    
    def __init__(self):
        self.console = Console()
        self.agent = None
        self.available_languages = None
        self.translation_tool = None
        
    def display_welcome(self):
        """Display welcome message and language capabilities."""
        welcome_text = """
[bold blue]Multi-Language Research Assistant[/bold blue]

This enhanced research assistant supports:
• [green]Research in 40+ Indo-European languages[/green]
• [green]Automatic translation of results[/green]
• [green]Language detection and smart routing[/green]
• [green]Multi-provider translation (Google, DeepL, Azure)[/green]
• [green]Translation caching for performance[/green]
• [green]Comprehensive research analytics[/green]
        """
        
        panel = Panel(
            welcome_text,
            title="🌍 Welcome",
            border_style="blue",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def display_supported_languages(self):
        """Display supported languages in a formatted table."""
        if not self.available_languages:
            return
        
        # Create language table
        table = Table(title="Supported Languages", show_header=True, header_style="bold magenta")
        table.add_column("Code", style="cyan", width=6)
        table.add_column("Language", style="green", width=20)
        table.add_column("Family", style="yellow", width=15)
        
        # Language families for organization
        language_families = {
            # Slavic
            'sl': ('Slovenian', 'Slavic'), 'hr': ('Croatian', 'Slavic'), 'sr': ('Serbian', 'Slavic'),
            'cs': ('Czech', 'Slavic'), 'pl': ('Polish', 'Slavic'), 'ru': ('Russian', 'Slavic'),
            'sk': ('Slovak', 'Slavic'), 'bg': ('Bulgarian', 'Slavic'),
            
            # Germanic
            'de': ('German', 'Germanic'), 'nl': ('Dutch', 'Germanic'), 'sv': ('Swedish', 'Germanic'),
            'no': ('Norwegian', 'Germanic'), 'da': ('Danish', 'Germanic'), 'is': ('Icelandic', 'Germanic'),
            'en': ('English', 'Germanic'),
            
            # Romance
            'it': ('Italian', 'Romance'), 'fr': ('French', 'Romance'), 'es': ('Spanish', 'Romance'),
            'pt': ('Portuguese', 'Romance'), 'ro': ('Romanian', 'Romance'), 'ca': ('Catalan', 'Romance'),
            
            # Celtic
            'ga': ('Irish', 'Celtic'), 'cy': ('Welsh', 'Celtic'), 'gd': ('Scottish Gaelic', 'Celtic'),
            
            # Other
            'el': ('Greek', 'Hellenic'), 'hi': ('Hindi', 'Indo-Aryan'), 'fa': ('Persian', 'Indo-Iranian'),
            'lt': ('Lithuanian', 'Baltic'), 'lv': ('Latvian', 'Baltic'), 'et': ('Estonian', 'Finno-Ugric'),
            'hu': ('Hungarian', 'Finno-Ugric'), 'fi': ('Finnish', 'Finno-Ugric')
        }
        
        # Sort by language family and then by language name
        sorted_langs = sorted(
            [(code, info[0], info[1]) for code, info in language_families.items()],
            key=lambda x: (x[2], x[1])
        )
        
        for code, name, family in sorted_langs:
            table.add_row(code, name, family)
        
        self.console.print(table)
    
    async def initialize_agent(self):
        """Initialize the multi-language research agent."""
        try:
            # Get API keys from environment
            openai_key = os.getenv("OPENAI_API_KEY")
            tavily_key = os.getenv("TAVILY_API_KEY")
            
            if not openai_key:
                self.console.print("[red]Error: OPENAI_API_KEY environment variable not set[/red]")
                return False
            
            if not tavily_key:
                self.console.print("[red]Error: TAVILY_API_KEY environment variable not set[/red]")
                return False
            
            # Initialize LLM client
            with self.console.status("Initializing AI models...", spinner="dots"):
                llm_client = create_llm_client("openai", api_key=openai_key)
            
            # Initialize translation tool
            with self.console.status("Initializing translation services...", spinner="dots"):
                self.translation_tool = TranslationTool()
                self.available_languages = self.translation_tool.get_supported_languages()
            
            # Initialize research agent
            with self.console.status("Initializing research agent...", spinner="dots"):
                self.agent = MultiLanguageResearchAgent(
                    name="MultiLangResearcher",
                    llm_client=llm_client,
                    default_language='en',
                    enable_translation=True
                )
            
            # Display initialization success
            providers = self.translation_tool.get_available_providers()
            self.console.print(f"[green]✓ Research agent initialized[/green]")
            self.console.print(f"[green]✓ Translation providers: {', '.join(providers)}[/green]")
            self.console.print(f"[green]✓ Supported languages: {len(self.available_languages)}[/green]")
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Failed to initialize agent: {str(e)}[/red]")
            return False
    
    def select_languages(self) -> tuple[str, List[str]]:
        """Allow user to select source and target languages."""
        if not self.available_languages:
            return 'en', ['en']
        
        # Display language selection
        self.console.print("\n[bold]Language Selection[/bold]")
        
        # Auto-detect or specify source language
        auto_detect = Confirm.ask("Auto-detect source language?", default=True)
        source_language = None
        
        if not auto_detect:
            self.console.print("\nAvailable languages:")
            lang_options = []
            for code, name in list(self.available_languages.items())[:20]:  # Show first 20
                lang_options.append(f"{code} ({name})")
                self.console.print(f"  {code}: {name}")
            
            source_language = Prompt.ask(
                "Enter source language code",
                default="en",
                choices=list(self.available_languages.keys())
            )
        
        # Select target languages for translation
        self.console.print("\n[bold]Translation Languages[/bold]")
        translate_results = Confirm.ask("Translate results to other languages?", default=False)
        
        target_languages = ['en']  # Always include English
        
        if translate_results:
            self.console.print("\nSelect target languages (comma-separated codes):")
            self.console.print("Popular options: en, es, fr, de, it, pt, sl, hr")
            
            lang_input = Prompt.ask(
                "Target language codes",
                default="en"
            )
            
            # Parse language codes
            target_languages = [lang.strip() for lang in lang_input.split(',')]
            
            # Validate language codes
            valid_languages = []
            for lang in target_languages:
                if lang in self.available_languages:
                    valid_languages.append(lang)
                else:
                    self.console.print(f"[yellow]Warning: {lang} not supported, skipping[/yellow]")
            
            target_languages = valid_languages if valid_languages else ['en']
        
        return source_language, target_languages
    
    def get_research_parameters(self) -> Dict[str, Any]:
        """Get research parameters from user."""
        self.console.print("\n[bold]Research Configuration[/bold]")
        
        # Research topic
        topic = normalize_text(Prompt.ask("Enter research topic"))
        
        # Smart language detection: if topic looks English, suggest it
        if topic.isascii() and any(word in topic.lower() for word in ['ai', 'the', 'and', 'or', 'in', 'on', 'with', 'trends']):
            self.console.print("[dim]💡 Topic appears to be in English[/dim]")
        
        # Focus areas (optional)
        focus_input = Prompt.ask(
            "Focus areas (comma-separated, optional)",
            default=""
        )
        focus_areas = [normalize_text(area.strip()) for area in focus_input.split(',') if area.strip()]
        
        # Search parameters
        max_queries = typer.prompt(
            "Maximum search queries",
            type=int,
            default=5
        )
        
        search_depth = Prompt.ask(
            "Search depth",
            choices=["basic", "advanced"],
            default="basic"
        )
        
        return {
            'topic': topic,
            'focus_areas': focus_areas if focus_areas else None,
            'max_queries': max_queries,
            'search_depth': search_depth
        }
    
    async def conduct_research(
        self,
        topic: str,
        source_language: Optional[str],
        target_languages: List[str],
        focus_areas: Optional[List[str]] = None,
        max_queries: int = 5,
        search_depth: str = "basic"
    ) -> Dict[str, Any]:
        """Conduct multi-language research with progress tracking."""
        
        # Create progress tracking
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console
        )
        
        with progress:
            # Add main research task
            research_task = progress.add_task(
                f"Researching: {topic[:50]}...",
                total=100
            )
            
            # Start research
            progress.update(research_task, advance=10, description="Detecting language...")
            
            try:
                result = await self.agent.conduct_multilang_research(
                    topic=topic,
                    focus_areas=focus_areas,
                    source_language=source_language,
                    target_languages=target_languages,
                    max_queries=max_queries,
                    search_depth=search_depth
                )
                
                progress.update(research_task, advance=90, description="Research completed!")
                
                return result
                
            except Exception as e:
                progress.update(research_task, description=f"Research failed: {str(e)}")
                raise
    
    def display_research_results(self, result: Dict[str, Any]):
        """Display research results in formatted output."""
        
        # Main research summary
        summary_panel = Panel(
            f"""[bold]Topic:[/bold] {result.get('topic', 'N/A')}
[bold]Status:[/bold] [green]{result.get('status', 'unknown')}[/green]
[bold]Processing Time:[/bold] {result.get('processing_time', 0):.1f}s
[bold]Queries:[/bold] {result.get('total_queries', 0)}
[bold]Sources:[/bold] {result.get('total_sources', 0)}""",
            title="📊 Research Summary",
            border_style="green"
        )
        self.console.print(summary_panel)
        
        # Language metadata
        if 'language_metadata' in result:
            lang_meta = result['language_metadata']
            lang_panel = Panel(
                f"""[bold]Original Language:[/bold] {lang_meta.get('original_language', 'auto-detected')}
[bold]Research Language:[/bold] {lang_meta.get('research_language', 'en')}
[bold]Target Languages:[/bold] {', '.join(lang_meta.get('target_languages', []))}
[bold]Translation Enabled:[/bold] {lang_meta.get('translation_enabled', False)}""",
                title="🌍 Language Information",
                border_style="blue"
            )
            self.console.print(lang_panel)
        
        # Executive summary
        if result.get('executive_summary'):
            summary_panel = Panel(
                result['executive_summary'],
                title="📋 Executive Summary",
                border_style="yellow"
            )
            self.console.print(summary_panel)
        
        # Key findings
        if result.get('key_findings'):
            findings_text = ""
            for i, finding in enumerate(result['key_findings'], 1):
                findings_text += f"{i}. {finding}\n"
            
            findings_panel = Panel(
                findings_text.strip(),
                title="🔍 Key Findings",
                border_style="cyan"
            )
            self.console.print(findings_panel)
        
        # Translation results  
        self.console.print(f"[dim]Debug: translations key exists: {'translations' in result}[/dim]")
        if 'translations' in result:
            self.console.print(f"[dim]Debug: translations content: {bool(result['translations'])}[/dim]")
            
        if 'translations' in result and result['translations']:
            self.console.print("\n[bold magenta]🔄 Translations[/bold magenta]")
            
            # Debug: Show what translations we have
            self.console.print(f"[dim]Found translations for: {list(result['translations'].keys())}[/dim]")
            
            for lang_code, translation in result['translations'].items():
                if 'error' in translation:
                    self.console.print(f"[red]{lang_code}: Translation failed - {translation['error']}[/red]")
                    continue
                
                lang_name = self.available_languages.get(lang_code, lang_code.upper())
                
                # Debug: Show translation structure
                self.console.print(f"[dim]{lang_code} translation keys: {list(translation.keys())}[/dim]")
                
                # Create translation panel
                trans_content = ""
                if 'executive_summary' in translation:
                    trans_content += f"[bold]Summary:[/bold]\n{translation['executive_summary'].get('text', 'N/A')}\n\n"
                
                if 'key_findings' in translation and translation['key_findings']:
                    trans_content += "[bold]Key Findings:[/bold]\n"
                    for i, finding in enumerate(translation['key_findings'], 1):
                        trans_content += f"{i}. {finding.get('text', finding.get('original', 'N/A'))}\n"
                
                if trans_content:
                    trans_panel = Panel(
                        trans_content.strip(),
                        title=f"📝 {lang_name} ({lang_code})",
                        border_style="magenta"
                    )
                    self.console.print(trans_panel)
    
    async def run_interactive_mode(self):
        """Run the interactive research session."""
        self.display_welcome()
        
        # Initialize agent
        if not await self.initialize_agent():
            return
        
        while True:
            try:
                self.console.print("\n" + "="*60)
                
                # Language selection
                source_language, target_languages = self.select_languages()
                
                # Research parameters
                params = self.get_research_parameters()
                
                # Confirm research
                self.console.print(f"\n[bold]Research Summary:[/bold]")
                self.console.print(f"Topic: {params['topic']}")
                self.console.print(f"Source Language: {source_language or 'auto-detect'}")
                self.console.print(f"Target Languages: {', '.join(target_languages)}")
                if params['focus_areas']:
                    self.console.print(f"Focus Areas: {', '.join(params['focus_areas'])}")
                
                if not Confirm.ask("\nProceed with research?"):
                    continue
                
                # Conduct research
                self.console.print("\n🔍 Starting research...")
                
                result = await self.conduct_research(
                    topic=params['topic'],
                    source_language=source_language,
                    target_languages=target_languages,
                    focus_areas=params['focus_areas'],
                    max_queries=params['max_queries'],
                    search_depth=params['search_depth']
                )
                
                # Display results
                self.console.print("\n" + "="*60)
                self.console.print("[bold green]✅ Research Completed![/bold green]")
                self.display_research_results(result)
                
                # Ask for another research
                if not Confirm.ask("\nConduct another research?"):
                    break
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Research interrupted by user[/yellow]")
                break
            except Exception as e:
                self.console.print(f"\n[red]Error: {str(e)}[/red]")
                if not Confirm.ask("Continue with another research?"):
                    break
        
        self.console.print("\n[bold blue]Thank you for using the Multi-Language Research Assistant![/bold blue]")


@app.command()
def interactive():
    """Run the interactive multi-language research session."""
    cli = MultiLangResearchCLI()
    asyncio.run(cli.run_interactive_mode())


@app.command()
def languages():
    """Display supported languages."""
    cli = MultiLangResearchCLI()
    
    # Initialize translation tool to get languages
    try:
        translation_tool = TranslationTool()
        cli.available_languages = translation_tool.get_supported_languages()
        cli.display_supported_languages()
        
        console.print(f"\n[green]Total supported languages: {len(cli.available_languages)}[/green]")
        
        # Show provider information
        providers = translation_tool.get_available_providers()
        console.print(f"[blue]Available translation providers: {', '.join(providers)}[/blue]")
        
    except Exception as e:
        console.print(f"[red]Error loading language information: {str(e)}[/red]")


@app.command()
def research(
    topic: str = typer.Argument(..., help="Research topic"),
    source_lang: str = typer.Option(None, "--source", "-s", help="Source language code"),
    target_langs: str = typer.Option("en", "--targets", "-t", help="Target language codes (comma-separated)"),
    max_queries: int = typer.Option(5, "--queries", "-q", help="Maximum number of queries"),
    depth: str = typer.Option("basic", "--depth", "-d", help="Search depth (basic or advanced)")
):
    """Conduct research with specified parameters."""
    
    async def run_research():
        # Validate depth parameter
        if depth not in ["basic", "advanced"]:
            console.print(f"[red]Error: depth must be 'basic' or 'advanced', got '{depth}'[/red]")
            return
            
        cli = MultiLangResearchCLI()
        
        # Initialize agent
        if not await cli.initialize_agent():
            return
        
        # Parse target languages
        target_languages = [lang.strip() for lang in target_langs.split(',')]
        
        # Conduct research
        console.print(f"[blue]Researching: {topic}[/blue]")
        
        result = await cli.conduct_research(
            topic=topic,
            source_language=source_lang,
            target_languages=target_languages,
            max_queries=max_queries,
            search_depth=depth
        )
        
        # Display results
        cli.display_research_results(result)
    
    asyncio.run(run_research())


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Application terminated by user.[/yellow]")
    except Exception as e:
        console.print(f"[red]Fatal error:[/red] {str(e)}")
        sys.exit(1)