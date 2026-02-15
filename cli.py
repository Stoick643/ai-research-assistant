#!/usr/bin/env python3
"""
CLI for AI Research Assistant.

Usage:
    python cli.py "quantum computing trends 2025"
    python cli.py "AI safety" --depth advanced --lang sl
    python cli.py "climate change" --focus "ocean,arctic" --output report.md
"""

import argparse
import asyncio
import io
import os
import sys
import time
from dotenv import load_dotenv

# Fix Windows terminal encoding for emoji/unicode
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.services.research_service import ResearchService

# Step icons for terminal display
STEP_ICONS = {
    'queued': '⏳',
    'initializing': '⚙️',
    'generating_queries': '🧠',
    'searching': '🔍',
    'analyzing': '📊',
    'writing_report': '📝',
    'saving': '💾',
    'translating': '🌐',
    'completed': '✅',
    'failed': '❌',
}


def print_progress(step, progress, message, detail='', preview='', **kwargs):
    """Print progress to terminal."""
    icon = STEP_ICONS.get(step, '•')
    bar_width = 30
    filled = int(bar_width * progress / 100)
    bar = '█' * filled + '░' * (bar_width - filled)
    print(f"\r  {icon} [{bar}] {progress:3d}% {message}", end='', flush=True)
    if detail:
        print(f" — {detail}", end='', flush=True)
    # New line when step changes significantly
    if step in ('searching', 'analyzing', 'writing_report', 'translating', 'completed', 'failed'):
        print()


def main():
    parser = argparse.ArgumentParser(
        description='AI Research Assistant — conduct web research from the command line',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py "quantum computing trends 2025"
  python cli.py "AI safety" --depth advanced
  python cli.py "climate change" --lang sl --focus "ocean,arctic"
  python cli.py "machine learning" --output report.md
        """
    )
    parser.add_argument('topic', help='Research topic (min 10 characters)')
    parser.add_argument('--depth', choices=['basic', 'advanced'], default='basic',
                       help='Search depth (default: basic)')
    parser.add_argument('--lang', default='en',
                       help='Target language code (default: en)')
    parser.add_argument('--focus', default='',
                       help='Focus areas, comma-separated')
    parser.add_argument('--output', '-o', default='',
                       help='Save report to file (markdown)')
    parser.add_argument('--no-cache', action='store_true',
                       help='Skip cache, force fresh research')
    
    args = parser.parse_args()
    
    if len(args.topic.strip()) < 10:
        print("❌ Topic must be at least 10 characters.")
        sys.exit(1)
    
    # Initialize service
    svc = ResearchService()
    keys = svc.resolve_keys()
    primary, fallback, final_fb = svc.resolve_providers(keys)
    
    if not primary:
        print("❌ No LLM provider available. Set at least one API key:")
        print("   OPENAI_API_KEY, DEEPSEEK_API_KEY, or ANTHROPIC_API_KEY")
        sys.exit(1)
    
    if not keys.get('tavily_api_key'):
        print("❌ No Tavily API key. Set TAVILY_API_KEY in .env")
        sys.exit(1)
    
    topic = args.topic.strip()
    language = args.lang
    depth = args.depth
    focus_areas = args.focus.strip()
    
    print(f"\n🔬 AI Research Assistant")
    print(f"{'=' * 50}")
    print(f"  Topic:    {topic}")
    print(f"  Depth:    {depth}")
    print(f"  Language: {language}")
    print(f"  Provider: {primary.title()}", end='')
    if fallback:
        print(f" → {fallback.title()}", end='')
    if final_fb:
        print(f" → {final_fb.title()}", end='')
    print()
    if focus_areas:
        print(f"  Focus:    {focus_areas}")
    print()
    
    # Cache check
    if not args.no_cache:
        cached = svc.find_cached(topic, language)
        if cached and cached['match_type'] == 'exact':
            age = svc.cache_age_minutes(cached['research'].get('completed_at'))
            print(f"📋 Found cached result from {age} minutes ago.")
            research = cached['research']
            content = research.get('report_content') or research.get('executive_summary', '')
            print(f"\n{content}")
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"\n💾 Saved to {args.output}")
            return
    
    # Create record and run
    research_id = svc.create_research_record(
        topic=topic, language=language, depth=depth,
        focus_areas=focus_areas, provider=primary,
    )
    
    # Progress callback for terminal
    last_step = [None]
    
    def on_progress(step, progress, message, detail='', preview=''):
        if step != last_step[0]:
            if last_step[0] is not None:
                print()  # New line for new step
            last_step[0] = step
        icon = STEP_ICONS.get(step, '•')
        bar_width = 30
        filled = int(bar_width * progress / 100)
        bar = '█' * filled + '░' * (bar_width - filled)
        line = f"\r  {icon} [{bar}] {progress:3d}% {message}"
        if detail:
            line += f" — {detail}"
        # Pad to clear previous line
        print(f"{line:<100}", end='', flush=True)
    
    start_time = time.time()
    
    try:
        # Check for translate-only path
        cached = None if args.no_cache else svc.find_cached(topic, language)
        
        if cached and cached.get('match_type') == 'english_available':
            print("📋 Found cached English research — translating...\n")
            english_research = cached['research']
            
            async def do_translation():
                svc._make_progress_callback(research_id)
                # Override with terminal callback
                orig_cb = svc._make_progress_callback(research_id)
                def combined(step, progress, message, detail='', preview=''):
                    orig_cb(step, progress, message, detail, preview)
                    on_progress(step, progress, message, detail, preview)
                
                # Monkey-patch the progress tracker callback
                old_tracker = svc.progress_tracker.get(research_id, {})
                await svc.run_translation(
                    research_id=research_id,
                    english_research=english_research,
                    language=language,
                    depth=depth,
                    resolved_keys=keys,
                )
            
            asyncio.run(do_translation())
        else:
            # Full research
            async def do_research():
                # Set up progress callback on the service
                real_cb = svc._make_progress_callback(research_id)
                # We need to also print to terminal, so wrap the agent's callback
                import types
                
                original_run = svc.run_research
                
                async def patched_run(**kwargs):
                    result = await original_run(**kwargs)
                    return result
                
                result = await svc.run_research(
                    research_id=research_id,
                    topic=topic,
                    language=language,
                    depth=depth,
                    focus_areas=focus_areas,
                    resolved_keys=keys,
                )
                return result
            
            # Patch the progress callback to also print to terminal
            orig_make_cb = svc._make_progress_callback
            def make_cb_with_print(rid):
                svc_cb = orig_make_cb(rid)
                def combined(step, progress, message, detail='', preview=''):
                    svc_cb(step, progress, message, detail, preview)
                    on_progress(step, progress, message, detail, preview)
                return combined
            svc._make_progress_callback = make_cb_with_print
            
            result = asyncio.run(svc.run_research(
                research_id=research_id,
                topic=topic,
                language=language,
                depth=depth,
                focus_areas=focus_areas,
                resolved_keys=keys,
            ))
        
        elapsed = time.time() - start_time
        print(f"\n\n{'=' * 50}")
        print(f"✅ Research completed in {elapsed:.1f}s")
        
        # Get the report content
        status = svc.get_status(research_id)
        content = ''
        if status:
            content = status.get('report_content') or status.get('executive_summary', '')
        elif 'result' in dir() and result:
            content = result.get('report_content', '')
        
        if content:
            print(f"\n{content}")
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"\n💾 Saved to {args.output}")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Research cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Research failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
