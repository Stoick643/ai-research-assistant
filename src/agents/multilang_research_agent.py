"""
Multi-language Research Agent with translation capabilities.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import structlog

from .research_agent import ResearchAgent
from ..tools.translation import TranslationTool
from ..tools.language_detection import detect_text_language

logger = structlog.get_logger()


class MultiLanguageResearchAgent(ResearchAgent):
    """
    Research agent with multi-language support and translation capabilities.
    
    Extends ResearchAgent to support:
    - Research in multiple languages
    - Automatic translation of queries and results
    - Language-aware research workflows
    - Multilingual report generation
    """
    
    def __init__(
        self, 
        name: str, 
        llm_client,
        web_search_tool=None,
        report_writer=None,
        sqlite_writer=None,
        enable_database_tracking: bool = True,
        default_language: str = 'en',
        target_languages: List[str] = None,
        enable_translation: bool = True
    ):
        """
        Initialize multi-language research agent.
        
        Args:
            name: Agent name
            llm_client: LLM client for reasoning
            web_search_tool: Web search tool (optional)
            report_writer: Report writer (optional) 
            sqlite_writer: SQLite writer for database tracking
            enable_database_tracking: Enable database tracking
            default_language: Default language for research ('en', 'sl', etc.)
            target_languages: List of languages to translate results to
            enable_translation: Enable translation capabilities
        """
        super().__init__(
            name=name,
            llm_client=llm_client,
            web_search_tool=web_search_tool,
            report_writer=report_writer,
            sqlite_writer=sqlite_writer,
            enable_database_tracking=enable_database_tracking
        )
        
        self.default_language = default_language
        self.target_languages = target_languages or [default_language]
        self.enable_translation = enable_translation
        
        # Initialize translation tool if enabled
        if self.enable_translation:
            try:
                self.translation_tool = TranslationTool(llm_client=llm_client)
                self.logger.info(
                    "Translation capabilities enabled",
                    default_language=default_language,
                    target_languages=self.target_languages,
                    providers=self.translation_tool.get_available_providers()
                )
            except Exception as e:
                self.logger.warning("Failed to initialize translation tool", error=str(e))
                self.translation_tool = None
                self.enable_translation = False
        else:
            self.translation_tool = None
    
    async def conduct_multilang_research(
        self,
        topic: str,
        focus_areas: List[str] = None,
        source_language: Optional[str] = None,
        target_languages: List[str] = None,
        max_queries: int = 5,
        search_depth: str = "basic"
    ) -> Dict[str, Any]:
        """
        Conduct research with multi-language support.
        
        Args:
            topic: Research topic
            focus_areas: Specific areas to focus on
            source_language: Source language of topic (auto-detect if None)
            target_languages: Languages to translate results to
            max_queries: Maximum number of search queries
            search_depth: Search depth (basic, advanced)
            
        Returns:
            Research results with translations
        """
        start_time = datetime.utcnow()
        
        # Use provided target languages or default
        target_langs = target_languages or self.target_languages
        
        # Detect source language if not provided
        if not source_language and self.enable_translation:
            # Quick heuristic: if text is mostly ASCII and English-like, assume English
            if topic.isascii() and any(word in topic.lower() for word in ['ai', 'trends', 'the', 'and', 'or', 'in', 'on', 'with']):
                source_language = 'en'
                self.logger.info("Assumed topic language (English keywords detected)", language=source_language)
            else:
                try:
                    source_language = await detect_text_language(topic)
                    self.logger.info("Detected topic language", language=source_language)
                except Exception as e:
                    self.logger.warning("Failed to detect topic language", error=str(e))
                    source_language = self.default_language
        else:
            source_language = source_language or self.default_language
        
        # Translate topic to default language for research if needed
        research_topic = topic
        if source_language != self.default_language and self.enable_translation:
            try:
                translation_result = await self.translation_tool.translate(
                    topic, 
                    self.default_language, 
                    source_language
                )
                research_topic = translation_result.translated_text
                self.logger.info(
                    "Translated topic for research",
                    original=topic,
                    translated=research_topic,
                    source_lang=source_language,
                    target_lang=self.default_language
                )
            except Exception as e:
                self.logger.warning("Failed to translate topic", error=str(e))
        
        # Conduct research in default language
        self.logger.info(
            "Starting multilingual research",
            topic=topic,
            research_topic=research_topic,
            source_language=source_language,
            target_languages=target_langs
        )
        
        research_result = await self.conduct_research(
            research_topic,
            focus_areas=focus_areas
        )
        
        # Add language metadata
        research_result['language_metadata'] = {
            'original_topic': topic,
            'original_language': source_language,
            'research_language': self.default_language,
            'target_languages': target_langs,
            'translation_enabled': self.enable_translation
        }
        
        # Translate results to target languages if needed
        if self.enable_translation and target_langs:
            translations = await self._translate_research_results(
                research_result,
                target_langs,
                source_language=self.default_language
            )
            research_result['translations'] = translations
            
            # Generate and save translated reports
            await self._save_multilingual_reports(research_result, target_langs)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        research_result['multilang_processing_time'] = processing_time
        
        self.logger.info(
            "Multilingual research completed",
            topic=topic,
            processing_time=processing_time,
            target_languages=len(target_langs) if target_langs else 0
        )
        
        return research_result
    
    async def _translate_research_results(
        self,
        research_result: Dict[str, Any],
        target_languages: List[str],
        source_language: str = 'en'
    ) -> Dict[str, Dict[str, Any]]:
        """
        Translate research results to multiple target languages.
        
        Args:
            research_result: Research results to translate
            target_languages: List of target language codes
            source_language: Source language of results
            
        Returns:
            Dictionary mapping language codes to translated content
        """
        translations = {}
        
        for target_lang in target_languages:
            if target_lang == source_language:
                # Skip translation for same language
                continue
            
            try:
                lang_translation = await self._translate_to_language(
                    research_result,
                    target_lang,
                    source_language
                )
                translations[target_lang] = lang_translation
                
                self.logger.info(
                    "Research translated",
                    target_language=target_lang,
                    sections_translated=len(lang_translation)
                )
                
            except Exception as e:
                self.logger.error(
                    "Failed to translate research results",
                    target_language=target_lang,
                    error=str(e)
                )
                translations[target_lang] = {
                    'error': f"Translation failed: {str(e)}",
                    'language': target_lang
                }
        
        return translations
    
    async def _translate_to_language(
        self,
        research_result: Dict[str, Any],
        target_language: str,
        source_language: str
    ) -> Dict[str, Any]:
        """
        Translate research result to a specific target language.
        
        Args:
            research_result: Research results to translate
            target_language: Target language code
            source_language: Source language code
            
        Returns:
            Translated research content
        """
        translation = {
            'language': target_language,
            'translated_at': datetime.utcnow().isoformat()
        }
        
        # Translate key sections - map actual research fields to translation keys
        sections_to_translate = [
            ('topic', 'topic'),
            ('analysis', 'executive_summary'),  # Research has 'analysis', CLI expects 'executive_summary'
            ('report_content', 'detailed_analysis')  # Research has 'report_content', CLI expects 'detailed_analysis'
        ]
        
        self.logger.info(f"Available research fields for translation: {list(research_result.keys())}")
        
        for source_key, target_key in sections_to_translate:
            if source_key in research_result and research_result[source_key]:
                try:
                    text_to_translate = research_result[source_key]
                    self.logger.info(f"Translating {source_key} ({len(str(text_to_translate))} chars) to {target_language}")
                    
                    result = await self.translation_tool.translate(
                        str(text_to_translate),
                        target_language,
                        source_language
                    )
                    translation[target_key] = {
                        'text': result.translated_text,
                        'confidence': result.confidence_score,
                        'provider': result.provider
                    }
                    self.logger.info(f"Successfully translated {source_key} to {target_language}")
                except Exception as e:
                    self.logger.warning(
                        f"Failed to translate {source_key}",
                        target_language=target_language,
                        error=str(e)
                    )
                    translation[target_key] = {
                        'text': str(text_to_translate),
                        'error': str(e)
                    }
            else:
                self.logger.warning(f"Field {source_key} missing or empty in research result")
        
        # Translate key findings if present
        if 'key_findings' in research_result and research_result['key_findings']:
            translated_findings = []
            for finding in research_result['key_findings']:
                try:
                    result = await self.translation_tool.translate(
                        finding,
                        target_language,
                        source_language
                    )
                    translated_findings.append({
                        'text': result.translated_text,
                        'confidence': result.confidence_score,
                        'original': finding
                    })
                except Exception as e:
                    self.logger.warning(
                        "Failed to translate finding",
                        finding=finding[:50],
                        error=str(e)
                    )
                    translated_findings.append({
                        'text': finding,
                        'error': str(e),
                        'original': finding
                    })
            
            translation['key_findings'] = translated_findings
        
        return translation
    
    async def generate_multilingual_report(
        self,
        research_result: Dict[str, Any],
        target_languages: List[str] = None,
        report_format: str = "markdown"
    ) -> Dict[str, str]:
        """
        Generate research reports in multiple languages.
        
        Args:
            research_result: Research results with translations
            target_languages: Languages to generate reports for
            report_format: Report format (markdown, html, etc.)
            
        Returns:
            Dictionary mapping language codes to report content
        """
        target_langs = target_languages or self.target_languages
        reports = {}
        
        # Generate report in default language
        default_report = await self._generate_report_content(research_result)
        reports[self.default_language] = default_report
        
        # Generate reports in other languages using translations
        if 'translations' in research_result:
            for lang_code, translation in research_result['translations'].items():
                if lang_code in target_langs:
                    try:
                        translated_report = await self._generate_translated_report(
                            research_result,
                            translation,
                            lang_code
                        )
                        reports[lang_code] = translated_report
                    except Exception as e:
                        self.logger.error(
                            "Failed to generate translated report",
                            language=lang_code,
                            error=str(e)
                        )
        
        self.logger.info(
            "Multilingual reports generated",
            languages=list(reports.keys()),
            report_count=len(reports)
        )
        
        return reports
    
    async def _generate_translated_report(
        self,
        original_result: Dict[str, Any],
        translation: Dict[str, Any],
        language: str
    ) -> str:
        """Generate report using translated content."""
        # Use the same report template but with translated content
        translated_result = original_result.copy()
        
        # Replace key sections with translations
        if 'topic' in translation:
            translated_result['topic'] = translation['topic'].get('text', original_result.get('topic', ''))
        
        if 'executive_summary' in translation:
            translated_result['executive_summary'] = translation['executive_summary'].get('text', '')
        
        if 'detailed_analysis' in translation:
            translated_result['detailed_analysis'] = translation['detailed_analysis'].get('text', '')
        
        if 'key_findings' in translation:
            translated_result['key_findings'] = [
                finding.get('text', finding.get('original', ''))
                for finding in translation['key_findings']
            ]
        
        # Generate report with translated content
        return await self._generate_report_content(translated_result)
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages for translation."""
        if self.translation_tool:
            return list(self.translation_tool.get_supported_languages().keys())
        return [self.default_language]
    
    def get_translation_providers(self) -> List[str]:
        """Get list of available translation providers."""
        if self.translation_tool:
            return self.translation_tool.get_available_providers()
        return []
    
    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translate text directly using the translation tool.
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language (auto-detect if None)
            
        Returns:
            Translation result dictionary
        """
        if not self.enable_translation or not self.translation_tool:
            raise ValueError("Translation not enabled or available")
        
        result = await self.translation_tool.translate(
            text, target_language, source_language
        )
        
        return {
            'original_text': result.original_text,
            'translated_text': result.translated_text,
            'source_language': result.source_language,
            'target_language': result.target_language,
            'confidence_score': result.confidence_score,
            'provider': result.provider,
            'processing_time': result.processing_time,
            'character_count': result.character_count
        }
    
    async def _save_multilingual_reports(
        self,
        research_result: Dict[str, Any],
        target_languages: List[str]
    ) -> None:
        """
        Save multilingual research reports to files.
        
        Args:
            research_result: Research results with translations
            target_languages: List of target language codes
        """
        self.logger.info(f"_save_multilingual_reports called with target_languages: {target_languages}")
        self.logger.info(f"Available translations: {list(research_result.get('translations', {}).keys())}")
        
        if not research_result.get('translations'):
            self.logger.warning("No translations found in research_result")
            return
        
        # Get topic for filename
        topic = research_result.get('topic', 'research')
        
        # Save each translation to a separate file
        for lang_code in target_languages:
            if lang_code not in research_result['translations']:
                self.logger.warning(f"Language {lang_code} not found in translations")
                continue
                
            translation = research_result['translations'][lang_code]
            if 'error' in translation:
                self.logger.error(f"Translation error for {lang_code}: {translation.get('error')}")
                continue
            
            self.logger.info(f"Processing translation for {lang_code}")
            self.logger.debug(f"Translation keys: {list(translation.keys())}")
            
            # Build content same as console display
            content = f"# Research Report: {topic}\n\n"
            content += f"**Language:** {lang_code}\n"
            content += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Add translated content
            if 'executive_summary' in translation:
                content += "## Summary\n\n"
                # Handle both string and dict formats
                if isinstance(translation['executive_summary'], dict):
                    summary_text = translation['executive_summary'].get('text', 'N/A')
                else:
                    summary_text = translation['executive_summary']
                content += f"{summary_text}\n\n"
            
            # Add detailed analysis if available
            if 'detailed_analysis' in translation:
                content += "## Detailed Analysis\n\n"
                if isinstance(translation['detailed_analysis'], dict):
                    analysis_text = translation['detailed_analysis'].get('text', 'N/A')
                else:
                    analysis_text = translation['detailed_analysis']
                content += f"{analysis_text}\n\n"
            
            # Save to reports directory  
            safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_topic = safe_topic.replace(' ', '_').lower()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"multilang_report_{safe_topic}_{timestamp}_{lang_code}.md"
            
            self.logger.info(f"Generated filename for {lang_code}: {filename}")
            
            self.logger.info(f"About to save {lang_code} report with filename: {filename}")
            self.logger.debug(f"Content length: {len(content)} characters")
            
            # Use the existing report_writer if available
            if hasattr(self, 'report_writer') and self.report_writer:
                try:
                    await self.report_writer.save_report(content, safe_topic, langCode=lang_code)
                    self.logger.info(f"✓ Successfully saved multilingual report via report_writer: {filename}")
                except Exception as e:
                    self.logger.error(f"✗ Failed to save report via report_writer {filename}: {str(e)}")
                    self.logger.exception("Full exception details:")
            else:
                # Fallback: save to reports directory
                import os
                reports_dir = os.path.join(os.getcwd(), 'reports')
                os.makedirs(reports_dir, exist_ok=True)
                
                filepath = os.path.join(reports_dir, filename)
                self.logger.info(f"Using fallback save to: {filepath}")
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.logger.info(f"✓ Successfully saved multilingual report via fallback: {filepath}")
                except Exception as e:
                    self.logger.error(f"✗ Failed to save report via fallback {filepath}: {str(e)}")
                    self.logger.exception("Full exception details:")