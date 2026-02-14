"""
Research agent implementation that extends ReasoningAgent for research workflows.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from .reasoning import ReasoningAgent
from ..tools.web_search import WebSearchTool, SearchResponse
from ..tools.report_writer import ReportWriter, MarkdownWriter, ReportFormatter
from ..database.sqlite_writer import SQLiteWriter
from ..utils.llm import LLMClient, normalize_text
import structlog

logger = structlog.get_logger()


class ResearchAgent(ReasoningAgent):
    """
    Research agent that combines web search capabilities with reasoning for comprehensive research.
    
    Extends ReasoningAgent to add:
    - Web search integration
    - Source analysis and synthesis
    - Structured report generation
    - Multi-stage research workflow
    """
    
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        web_search_tool: Optional[WebSearchTool] = None,
        report_writer: Optional[ReportWriter] = None,
        sqlite_writer: Optional[SQLiteWriter] = None,
        description: str = "An AI research agent that conducts web research and generates comprehensive reports",
        max_search_queries: int = 5,
        enable_database_tracking: bool = True,
        **kwargs
    ):
        super().__init__(name, llm_client, description, **kwargs)
        
        # Initialize tools
        self.web_search_tool = web_search_tool or WebSearchTool()
        self.report_writer = report_writer or MarkdownWriter()
        self.sqlite_writer = sqlite_writer or (SQLiteWriter() if enable_database_tracking else None)
        self.max_search_queries = max_search_queries
        self.enable_database_tracking = enable_database_tracking
        
        # Research tracking
        self.research_queries = []
        self.all_search_results = []
        self.all_search_responses = []
        self.research_start_time = None
        self.current_research_id = None
        self.progress_callback = None  # Optional callback for live progress
        
        self.logger = logger.bind(agent=name, type="research")
    
    def _report_progress(self, step: str, progress: int, message: str, detail: str = '', preview: str = ''):
        """Report progress via callback if set."""
        if self.progress_callback:
            try:
                self.progress_callback(step=step, progress=progress, message=message, detail=detail, preview=preview)
            except Exception as e:
                self.logger.warning("Progress callback failed", error=str(e))
    
    async def conduct_research(self, topic: str, focus_areas: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Main research pipeline that conducts comprehensive research on a topic.
        
        Args:
            topic: The research topic
            focus_areas: Optional list of specific areas to focus on
            
        Returns:
            Dictionary containing research results and metadata
        """
        # Normalize input text to handle Unicode issues
        topic = normalize_text(topic)
        if focus_areas:
            focus_areas = [normalize_text(area) for area in focus_areas]
        
        self.research_start_time = time.time()
        start_datetime = datetime.utcnow()
        self.logger.info("Starting research", topic=topic, focus_areas=focus_areas)
        
        # Reset tracking variables for new research session
        self.research_queries = []
        self.all_search_results = []
        self.all_search_responses = []
        self.current_research_id = None
        
        try:
            # Phase 1: Generate research queries
            self._report_progress('generating_queries', 10, 'Generating search queries...', f'Topic: {topic[:80]}')
            search_queries = await self._generate_search_queries(topic, focus_areas)
            self._report_progress('searching', 20, f'Starting web search...', f'{len(search_queries)} queries planned')
            
            # Phase 2: Execute web searches
            all_results = await self._execute_searches(search_queries)
            
            # Phase 3: Analyze and synthesize sources
            self._report_progress('analyzing', 60, f'Analyzing {len(self.all_search_results)} sources...', 'Synthesizing findings')
            analysis = await self._analyze_sources(topic, all_results)
            
            # Phase 4: Generate structured report
            self._report_progress('writing_report', 75, 'Writing research report...', 'Structuring findings into report')
            report_content = await self._generate_report(topic, analysis, all_results)
            
            # Phase 5: Save report (includes database tracking)
            self._report_progress('saving', 90, 'Saving report...', '')
            processing_time = time.time() - self.research_start_time
            report_path = await self._save_research_report(
                topic, report_content, processing_time, 
                start_datetime, focus_areas, analysis
            )
            
            research_result = {
                "topic": topic,
                "report_path": report_path,
                "report_content": report_content,
                "total_queries": len(self.research_queries),
                "total_sources": len(self.all_search_results),
                "processing_time": processing_time,
                "analysis": analysis,
                "search_queries": search_queries,
                "research_id": self.current_research_id
            }
            
            self.logger.info(
                "Research completed",
                topic=topic,
                queries=len(self.research_queries),
                sources=len(self.all_search_results),
                processing_time=processing_time,
                report_path=report_path
            )
            
            return research_result
            
        except Exception as e:
            self.logger.error("Research failed", topic=topic, error=str(e))
            raise RuntimeError(f"Research failed: {str(e)}") from e
    
    async def _generate_search_queries(self, topic: str, focus_areas: Optional[List[str]] = None) -> List[str]:
        """Generate targeted search queries for the research topic."""
        focus_context = ""
        if focus_areas:
            focus_context = f"Focus particularly on these areas: {', '.join(focus_areas)}"
        
        query_prompt = f"""
        Research Topic: {topic}
        {focus_context}
        
        Generate {self.max_search_queries} specific, targeted search queries that will help gather comprehensive information about this topic.
        
        Each query should:
        1. Be specific and focused
        2. Cover different aspects of the topic
        3. Use effective search terms
        4. Avoid overly broad or vague terms
        
        Return only the search queries, one per line, without numbering or formatting.
        """
        
        response = await self.llm_client.generate(
            system_prompt="You are a research assistant specialized in creating effective search queries.",
            user_message=query_prompt
        )
        
        # Parse queries from response
        queries = []
        for line in response.strip().split('\n'):
            query = line.strip()
            if query and not query.startswith(('1.', '2.', '3.', '4.', '5.')):
                queries.append(query)
            elif query:
                # Remove numbering if present
                parts = query.split('.', 1)
                if len(parts) > 1:
                    queries.append(parts[1].strip())
        
        # Limit to max queries
        queries = queries[:self.max_search_queries]
        
        self.logger.info("Generated search queries", topic=topic, query_count=len(queries))
        return queries
    
    async def _execute_searches(self, queries: List[str]) -> List[SearchResponse]:
        """Execute web searches sequentially for live progress updates."""
        self.logger.info("Executing web searches", query_count=len(queries))
        
        total = len(queries)
        successful_responses = []
        preview_parts = []
        
        # Sequential execution — each search reports progress with preview
        for i, query in enumerate(queries):
            query_num = i + 1
            # Progress: 20% to 50% spread across searches
            search_progress = 20 + int(30 * query_num / total)
            
            self._report_progress(
                'searching', search_progress - 5,
                f'Searching {query_num}/{total}: "{query[:60]}"',
                f'{len(self.all_search_results)} sources found so far',
                preview='\n\n---\n\n'.join(preview_parts) if preview_parts else ''
            )
            
            try:
                response = await self.web_search_tool.search(
                    query=query,
                    max_results=5,
                    search_depth="basic",
                    include_answer=True
                )
                
                successful_responses.append(response)
                self.research_queries.append(query)
                self.all_search_results.extend(response.results)
                self.all_search_responses.append(response)
                
                # Add Tavily AI answer to rolling preview
                if response.answer:
                    preview_parts.append(f"**{query}**\n\n{response.answer}")
                
                self._report_progress(
                    'searching', search_progress,
                    f'Search {query_num}/{total} done — {len(response.results)} results',
                    f'{len(self.all_search_results)} total sources',
                    preview='\n\n---\n\n'.join(preview_parts)
                )
                
                self.logger.info(
                    "Search completed",
                    query=query, query_num=query_num, total=total,
                    results=len(response.results),
                    has_answer=bool(response.answer)
                )
                
            except Exception as e:
                self.logger.warning("Search failed", query=query, error=str(e))
        
        self.logger.info(
            "All web searches completed",
            total_queries=total,
            successful=len(successful_responses),
            total_results=len(self.all_search_results)
        )
        
        return successful_responses
    
    async def analyze_sources(self, topic: str, search_responses: List[SearchResponse]) -> str:
        """Analyze and synthesize information from search results (public method)."""
        return await self._analyze_sources(topic, search_responses)
    
    async def _analyze_sources(self, topic: str, search_responses: List[SearchResponse]) -> str:
        """Analyze and synthesize information from search results."""
        self.logger.info("Analyzing sources", topic=topic, source_count=len(self.all_search_results))
        
        # Prepare source content for analysis
        sources_content = ""
        for i, response in enumerate(search_responses):
            sources_content += f"\n\n=== Search Query: {response.query} ===\n"
            
            if response.answer:
                sources_content += f"AI Answer: {response.answer}\n\n"
            
            for j, result in enumerate(response.results):
                sources_content += f"Source {i+1}.{j+1}: {result.title}\n"
                sources_content += f"URL: {result.url}\n"
                sources_content += f"Content: {result.content[:500]}...\n"
                sources_content += f"Relevance Score: {result.score}\n\n"
        
        analysis_prompt = f"""
        Research Topic: {topic}
        
        Below are search results from multiple queries. Please analyze and synthesize this information to provide:
        
        1. A comprehensive executive summary (2-3 paragraphs)
        2. 3-5 key findings with supporting evidence
        3. Detailed analysis organized by themes or subtopics
        4. Identification of any gaps or contradictions in the information
        
        Source Material:
        {sources_content[:8000]}  # Limit content to avoid token limits
        
        Provide a thorough, well-structured analysis that synthesizes information across all sources.
        """
        
        system_prompt = "You are an expert research analyst. Synthesize information from multiple sources into a comprehensive analysis."
        
        # Use streaming if progress callback is set and client supports it
        if self.progress_callback and hasattr(self.llm_client, 'generate_stream'):
            last_update = [time.time()]
            start_time = time.time()
            
            def on_chunk(chunk, accumulated):
                now = time.time()
                # Update preview every ~1s to keep UI flowing smoothly
                if now - last_update[0] >= 1.0:
                    last_update[0] = now
                    elapsed = int(now - start_time)
                    self._report_progress(
                        'analyzing', 65,
                        f'Analyzing {len(self.all_search_results)} sources... ({elapsed}s)',
                        f'{len(accumulated)} characters generated',
                        preview=f'## 📊 Analysis\n\n{accumulated}'
                    )
            
            analysis = await self.llm_client.generate_stream(
                system_prompt=system_prompt,
                user_message=analysis_prompt,
                on_chunk=on_chunk,
                max_tokens=2000,
                temperature=0.3
            )
            
            # Final update with complete analysis
            self._report_progress(
                'analyzing', 72,
                'Analysis complete — preparing report...',
                f'{len(analysis)} characters',
                preview=f'## 📊 Analysis\n\n{analysis}'
            )
        else:
            analysis = await self.llm_client.generate(
                system_prompt=system_prompt,
                user_message=analysis_prompt,
                max_tokens=2000,
                temperature=0.3
            )
        
        self.logger.info("Source analysis completed", topic=topic, analysis_length=len(analysis))
        return analysis
    
    async def generate_report(self, topic: str, analysis: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generate structured report (public method)."""
        search_responses = getattr(self, '_last_search_responses', [])
        return await self._generate_report(topic, analysis, search_responses, metadata)
    
    async def _generate_report(self, topic: str, analysis: str, search_responses: List[SearchResponse], metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generate structured markdown report."""
        self.logger.info("Generating report", topic=topic)
        
        # Extract key findings from analysis (streams to preview)
        self._report_progress('writing_report', 78, 'Extracting key findings...', '', 
                            preview=f'## 📊 Analysis\n\n{analysis}')
        key_findings = await self._extract_key_findings(analysis)
        
        # Show key findings in preview while executive summary generates
        findings_preview = '\n'.join(f'- {f}' for f in key_findings)
        self._report_progress('writing_report', 80, 
                            f'Found {len(key_findings)} key findings — writing summary...', '',
                            preview=f'## 🔑 Key Findings\n\n{findings_preview}')
        
        # Prepare sources list
        sources = []
        seen_urls = set()
        for response in search_responses:
            for result in response.results:
                if result.url not in seen_urls:
                    sources.append({
                        'title': result.title,
                        'url': result.url,
                        'score': result.score
                    })
                    seen_urls.add(result.url)
        
        # Sort sources by relevance score
        sources.sort(key=lambda x: x['score'], reverse=True)
        
        # Calculate processing time
        processing_time = time.time() - self.research_start_time if self.research_start_time else 0
        
        # Generate executive summary from analysis (streams to preview)
        executive_summary = await self._extract_executive_summary(analysis, stream_to_preview=True)
        
        # Format report using the standard template
        self._report_progress('writing_report', 88, 'Formatting final report...', f'{len(sources)} sources cited',
                            preview=f'## ✍️ Executive Summary\n\n{executive_summary}\n\n## 🔑 Key Findings\n\n{findings_preview}')
        report_content = ReportFormatter.format_research_report(
            topic=topic,
            executive_summary=executive_summary,
            key_findings=key_findings,
            detailed_analysis=analysis,
            sources=sources,
            query_count=len(self.research_queries),
            processing_time=processing_time
        )
        
        self.logger.info("Report generated", topic=topic, content_length=len(report_content))
        return report_content
    
    async def _extract_key_findings(self, analysis: str) -> List[str]:
        """Extract key findings from the analysis."""
        prompt = f"""
        From the following analysis, extract 3-5 key findings. Each finding should be:
        - Concise (1-2 sentences)
        - Specific and actionable
        - Supported by the analysis
        
        Analysis:
        {analysis[:2000]}
        
        Return only the key findings, one per line, without numbering or bullets.
        """
        
        response = await self.llm_client.generate(
            system_prompt="You are a research summarizer. Extract the most important findings from research analysis.",
            user_message=prompt,
            max_tokens=500,
            temperature=0.2
        )
        
        findings = []
        for line in response.strip().split('\n'):
            finding = line.strip()
            if finding and not finding.startswith(('-', '•', '1.', '2.', '3.', '4.', '5.')):
                findings.append(finding)
            elif finding:
                # Remove formatting if present
                clean_finding = finding.lstrip('-•').strip()
                if clean_finding and not clean_finding[0].isdigit():
                    findings.append(clean_finding)
                elif clean_finding:
                    parts = clean_finding.split('.', 1)
                    if len(parts) > 1:
                        findings.append(parts[1].strip())
        
        return findings[:5]  # Limit to 5 findings
    
    async def _extract_executive_summary(self, analysis: str, stream_to_preview: bool = False) -> str:
        """Extract executive summary from the analysis."""
        prompt = f"""
        From the following analysis, create a concise executive summary (2-3 paragraphs) that:
        - Provides a high-level overview
        - Highlights the most important insights
        - Is accessible to a general audience
        
        Analysis:
        {analysis[:2000]}
        
        Return only the executive summary without headers or formatting.
        """
        
        system_prompt = "You are a research writer. Create executive summaries that distill complex analysis into clear, accessible overviews."
        
        # Stream if we have a callback and the client supports it
        if stream_to_preview and self.progress_callback and hasattr(self.llm_client, 'generate_stream'):
            last_update = [time.time()]
            
            def on_chunk(chunk, accumulated):
                now = time.time()
                if now - last_update[0] >= 1.0:
                    last_update[0] = now
                    self._report_progress(
                        'writing_report', 85,
                        'Writing executive summary...',
                        f'{len(accumulated)} characters',
                        preview=f'## ✍️ Executive Summary\n\n{accumulated}'
                    )
            
            summary = await self.llm_client.generate_stream(
                system_prompt=system_prompt,
                user_message=prompt,
                on_chunk=on_chunk,
                max_tokens=400,
                temperature=0.3
            )
        else:
            summary = await self.llm_client.generate(
                system_prompt=system_prompt,
                user_message=prompt,
                max_tokens=400,
                temperature=0.3
            )
        
        return summary.strip()
    
    async def _save_research_report(
        self, 
        topic: str, 
        report_content: str, 
        processing_time: float,
        start_datetime: datetime,
        focus_areas: Optional[List[str]] = None,
        analysis: str = ""
    ) -> str:
        """Save the research report using the report writer and optionally to database."""
        filename = f"research_report_{topic.replace(' ', '_').lower()}"
        
        # Prepare metadata for regular report writer
        basic_metadata = {
            "research_date": datetime.now(),
            "query_count": len(self.research_queries),
            "source_count": len(self.all_search_results),
            "processing_time": processing_time,
            "agent_name": self.name
        }
        
        # Save to regular report writer (markdown)
        report_path = await self.report_writer.save_report(
            content=report_content,
            filename=filename,
            metadata=basic_metadata
        )
        
        # Save to database if SQLite tracking is enabled
        if self.enable_database_tracking and self.sqlite_writer:
            try:
                # Extract key findings from analysis
                key_findings = await self._extract_key_findings(analysis) if analysis else []
                executive_summary = await self._extract_executive_summary(analysis) if analysis else ""
                
                # Prepare comprehensive research data for database
                research_data = {
                    "topic": topic,
                    "focus_areas": focus_areas,
                    "agent_name": self.name,
                    "started_at": start_datetime,
                    "completed_at": datetime.utcnow(),
                    "processing_time": processing_time,
                    "executive_summary": executive_summary,
                    "key_findings": key_findings,
                    "detailed_analysis": analysis,
                    "report_path": report_path,
                    "total_queries": len(self.research_queries),
                    "total_sources": len(self.all_search_results),
                    "queries": self._prepare_queries_for_database(),
                    "additional_metadata": {
                        "max_search_queries": self.max_search_queries,
                        "agent_description": self.description
                    }
                }
                
                # Save to database
                db_result = await self.sqlite_writer.save_report(
                    content=report_content,
                    filename=filename,
                    metadata={"research_data": research_data}
                )
                
                # Extract research ID from database result
                if db_result.startswith("research_id:"):
                    self.current_research_id = int(db_result.split(":")[1])
                    self.logger.info("Research saved to database", 
                                   research_id=self.current_research_id)
                
            except Exception as e:
                self.logger.error("Failed to save research to database", error=str(e))
                # Don't fail the entire research process if database save fails
        
        return report_path
    
    def _prepare_queries_for_database(self) -> List[Dict[str, Any]]:
        """Prepare query data for database storage."""
        queries_data = []
        
        for i, (query_text, response) in enumerate(zip(self.research_queries, self.all_search_responses)):
            query_data = {
                "query_text": query_text,
                "executed_at": datetime.utcnow(),
                "max_results": 5,  # Default from search calls
                "search_depth": "basic",
                "include_answer": True,
                "results_count": len(response.results),
                "ai_answer": response.answer,
                "follow_up_questions": response.follow_up_questions or [],
                "search_context": response.search_context,
                "execution_time": 0.0,  # TODO: Track individual query times
                "success": True,
                "error_message": None,
                "sources": [
                    {
                        "title": result.title,
                        "url": result.url,
                        "content": result.content,
                        "score": result.score,
                        "published_date": result.published_date
                    }
                    for result in response.results
                ]
            }
            queries_data.append(query_data)
        
        return queries_data
    
    # Override parent methods to integrate research capabilities
    
    async def plan(self, goal: str) -> List[str]:
        """Create a research plan for the given goal."""
        if "research" in goal.lower():
            return [
                "Generate targeted search queries",
                "Execute web searches",
                "Analyze and synthesize sources",
                "Generate structured report",
                "Save research report"
            ]
        else:
            # Fall back to parent implementation
            return await super().plan(goal)
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """Execute research-specific tasks."""
        if "research" in task.lower():
            # Extract topic from task
            topic = task.replace("research", "").strip()
            if not topic:
                topic = "general inquiry"
            
            result = await self.conduct_research(topic)
            return {
                "task": task,
                "status": "completed",
                "result": f"Research completed on '{topic}'. Report saved to: {result['report_path']}",
                "metadata": {
                    "report_path": result["report_path"],
                    "query_count": result["total_queries"],
                    "source_count": result["total_sources"],
                    "processing_time": result["processing_time"]
                }
            }
        else:
            # Fall back to parent implementation
            return await super().execute_task(task)