"""
Mock translation provider for testing without Google Cloud credentials.
"""

import asyncio
import time
from typing import List, Optional

from ..translation import (
    TranslationProvider, 
    TranslationResult, 
    LanguageDetectionResult,
    TranslationError
)


class MockTranslateProvider(TranslationProvider):
    """Mock translation provider for testing purposes."""
    
    # Simple translation dictionary for common words
    TRANSLATIONS = {
        ('en', 'sl'): {
            'AI trends': 'AI trendi',
            'artificial intelligence': 'umetna inteligenca',
            'machine learning': 'strojno učenje',
            'Large Language Models': 'Veliki jezikovni modeli',
            'technology': 'tehnologija',
            'future': 'prihodnost',
            'development': 'razvoj',
            'innovation': 'inovacija',
            'research': 'raziskava',
            'analysis': 'analiza',
        },
        ('en', 'de'): {
            'AI trends': 'KI-Trends',
            'artificial intelligence': 'künstliche Intelligenz',
            'machine learning': 'maschinelles Lernen',
            'Large Language Models': 'Große Sprachmodelle',
            'technology': 'Technologie',
            'future': 'Zukunft',
            'development': 'Entwicklung',
            'innovation': 'Innovation',
            'research': 'Forschung',
            'analysis': 'Analyse',
        }
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger.info("Mock translation provider initialized")
    
    def _simple_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Simple word-based translation using dictionary."""
        if source_lang == target_lang:
            return text
        
        translations = self.TRANSLATIONS.get((source_lang, target_lang), {})
        translated_text = text
        
        for english, foreign in translations.items():
            translated_text = translated_text.replace(english, foreign)
        
        # Add a note that this is mock translation
        translated_text += f" [Mock translation {source_lang}→{target_lang}]"
        
        return translated_text
    
    async def translate(
        self, 
        text: str, 
        target_language: str, 
        source_language: Optional[str] = None
    ) -> TranslationResult:
        """Mock translation implementation."""
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        source_lang = source_language or 'en'
        
        if source_lang == target_language:
            translated_text = text
        else:
            translated_text = self._simple_translate(text, source_lang, target_language)
        
        return TranslationResult(
            original_text=text,
            translated_text=translated_text,
            source_language=source_lang,
            target_language=target_language,
            confidence_score=0.8,  # Mock confidence
            provider='mock',
            processing_time=0.1,
            character_count=len(text)
        )
    
    async def detect_language(self, text: str) -> LanguageDetectionResult:
        """Mock language detection."""
        
        # Simple heuristic: if text contains Slovenian characters, it's Slovenian
        if any(char in text for char in ['č', 'š', 'ž', 'Č', 'Š', 'Ž']):
            detected_lang = 'sl'
            confidence = 0.9
        # If text contains German characters, it's German
        elif any(char in text for char in ['ä', 'ö', 'ü', 'ß', 'Ä', 'Ö', 'Ü']):
            detected_lang = 'de'
            confidence = 0.9
        else:
            # Default to English
            detected_lang = 'en'
            confidence = 0.8
        
        return LanguageDetectionResult(
            text=text,
            detected_language=detected_lang,
            confidence_score=confidence,
            provider='mock'
        )
    
    async def get_supported_languages(self) -> List[str]:
        """Return mock supported languages."""
        return ['en', 'sl', 'de', 'fr', 'es', 'it']
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Mock Translator"
    
    async def translate_batch(
        self, 
        texts: List[str], 
        target_language: str, 
        source_language: Optional[str] = None
    ) -> List[TranslationResult]:
        """Mock batch translation."""
        results = []
        for text in texts:
            result = await self.translate(text, target_language, source_language)
            results.append(result)
        return results