"""
Language detection utilities using langdetect as fallback.
"""

import asyncio
from typing import List, Dict, Optional
import structlog

try:
    from langdetect import detect, detect_langs, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    LANGDETECT_AVAILABLE = True
    # Set seed for consistent results
    DetectorFactory.seed = 0
except ImportError:
    LANGDETECT_AVAILABLE = False

from .translation import LanguageDetectionResult, TranslationError

logger = structlog.get_logger()


class LanguageDetector:
    """Standalone language detection using langdetect library."""
    
    # Language code mapping from langdetect to our standard codes
    LANGDETECT_MAPPING = {
        'af': 'af',      # Afrikaans (not in our list but supported)
        'ar': 'ar',      # Arabic (not in our list but supported)
        'bg': 'bg',      # Bulgarian
        'bn': 'bn',      # Bengali (not in our list but supported)
        'ca': 'ca',      # Catalan
        'cs': 'cs',      # Czech
        'cy': 'cy',      # Welsh
        'da': 'da',      # Danish
        'de': 'de',      # German
        'el': 'el',      # Greek
        'en': 'en',      # English
        'es': 'es',      # Spanish
        'et': 'et',      # Estonian
        'fa': 'fa',      # Persian
        'fi': 'fi',      # Finnish
        'fr': 'fr',      # French
        'gu': 'gu',      # Gujarati (not in our list but supported)
        'he': 'he',      # Hebrew (not in our list but supported)
        'hi': 'hi',      # Hindi
        'hr': 'hr',      # Croatian
        'hu': 'hu',      # Hungarian
        'id': 'id',      # Indonesian (not in our list but supported)
        'it': 'it',      # Italian
        'ja': 'ja',      # Japanese (not in our list but supported)
        'kn': 'kn',      # Kannada (not in our list but supported)
        'ko': 'ko',      # Korean (not in our list but supported)
        'lt': 'lt',      # Lithuanian
        'lv': 'lv',      # Latvian
        'mk': 'mk',      # Macedonian (not in our list but supported)
        'ml': 'ml',      # Malayalam (not in our list but supported)
        'mr': 'mr',      # Marathi (not in our list but supported)
        'ne': 'ne',      # Nepali (not in our list but supported)
        'nl': 'nl',      # Dutch
        'no': 'no',      # Norwegian
        'pa': 'pa',      # Punjabi (not in our list but supported)
        'pl': 'pl',      # Polish
        'pt': 'pt',      # Portuguese
        'ro': 'ro',      # Romanian
        'ru': 'ru',      # Russian
        'sk': 'sk',      # Slovak
        'sl': 'sl',      # Slovenian
        'so': 'so',      # Somali (not in our list but supported)
        'sq': 'sq',      # Albanian (not in our list but supported)
        'sv': 'sv',      # Swedish
        'sw': 'sw',      # Swahili (not in our list but supported)
        'ta': 'ta',      # Tamil (not in our list but supported)
        'te': 'te',      # Telugu (not in our list but supported)
        'th': 'th',      # Thai (not in our list but supported)
        'tl': 'tl',      # Filipino (not in our list but supported)
        'tr': 'tr',      # Turkish (not in our list but supported)
        'uk': 'uk',      # Ukrainian (not in our list but supported)
        'ur': 'ur',      # Urdu (not in our list but supported)
        'vi': 'vi',      # Vietnamese (not in our list but supported)
        'zh-cn': 'zh',   # Chinese Simplified (not in our list but supported)
        'zh-tw': 'zh',   # Chinese Traditional (not in our list but supported)
    }
    
    def __init__(self):
        """Initialize language detector."""
        self.logger = logger.bind(component="language_detector")
        
        if not LANGDETECT_AVAILABLE:
            self.logger.warning("langdetect library not available. Install with: pip install langdetect")
    
    async def detect_language(self, text: str) -> LanguageDetectionResult:
        """
        Detect language of text using langdetect.
        
        Args:
            text: Text to analyze
            
        Returns:
            LanguageDetectionResult with detected language and confidence
        """
        if not text.strip():
            return LanguageDetectionResult(
                text=text,
                detected_language='unknown',
                confidence_score=0.0,
                provider='langdetect'
            )
        
        if not LANGDETECT_AVAILABLE:
            raise TranslationError(
                "langdetect library not available. Cannot perform language detection.",
                provider="langdetect"
            )
        
        try:
            # Run detection in thread pool since langdetect is synchronous
            detected_lang = await asyncio.get_event_loop().run_in_executor(
                None, detect, text
            )
            
            # Get probabilities for confidence and alternatives
            lang_probs = await asyncio.get_event_loop().run_in_executor(
                None, detect_langs, text
            )
            
            # Map to our standard language codes
            standard_lang = self.LANGDETECT_MAPPING.get(detected_lang, detected_lang)
            
            # Find confidence for the detected language
            confidence = 0.0
            alternatives = []
            
            for prob in lang_probs:
                lang_code = self.LANGDETECT_MAPPING.get(prob.lang, prob.lang)
                if prob.lang == detected_lang:
                    confidence = prob.prob
                else:
                    alternatives.append({lang_code: prob.prob})
            
            self.logger.info(
                "Language detected",
                language=standard_lang,
                confidence=confidence,
                char_count=len(text)
            )
            
            return LanguageDetectionResult(
                text=text,
                detected_language=standard_lang,
                confidence_score=confidence,
                provider='langdetect',
                alternative_languages=alternatives[:5]  # Top 5 alternatives
            )
            
        except LangDetectException as e:
            self.logger.warning("Language detection failed", error=str(e))
            return LanguageDetectionResult(
                text=text,
                detected_language='unknown',
                confidence_score=0.0,
                provider='langdetect'
            )
        except Exception as e:
            raise TranslationError(f"Language detection error: {str(e)}", provider="langdetect")
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        return list(self.LANGDETECT_MAPPING.values())
    
    async def detect_language_batch(self, texts: List[str]) -> List[LanguageDetectionResult]:
        """
        Detect languages for multiple texts.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of LanguageDetectionResult objects
        """
        results = []
        for text in texts:
            result = await self.detect_language(text)
            results.append(result)
        return results


# Convenience function for quick language detection
async def detect_text_language(text: str) -> str:
    """
    Quick language detection returning just the language code.
    
    Args:
        text: Text to analyze
        
    Returns:
        Detected language code or 'unknown'
    """
    detector = LanguageDetector()
    try:
        result = await detector.detect_language(text)
        return result.detected_language
    except Exception:
        return 'unknown'