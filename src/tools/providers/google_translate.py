"""
Google Translate API provider for translation services.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
import structlog

try:
    from google.cloud import translate_v2 as translate
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from ..translation import (
    TranslationProvider, 
    TranslationResult, 
    LanguageDetectionResult,
    TranslationError,
    ProviderUnavailableError,
    RateLimitError,
    UnsupportedLanguageError
)

logger = structlog.get_logger()


class GoogleTranslateProvider(TranslationProvider):
    """Google Translate API implementation."""
    
    # Language code mapping (Google uses some different codes)
    LANGUAGE_MAPPING = {
        # Map our standard codes to Google's codes
        'sl': 'sl',  # Slovenian
        'hr': 'hr',  # Croatian
        'sr': 'sr',  # Serbian
        'cs': 'cs',  # Czech
        'pl': 'pl',  # Polish
        'ru': 'ru',  # Russian
        'sk': 'sk',  # Slovak
        'bg': 'bg',  # Bulgarian
        'de': 'de',  # German
        'nl': 'nl',  # Dutch
        'sv': 'sv',  # Swedish
        'no': 'no',  # Norwegian
        'da': 'da',  # Danish
        'is': 'is',  # Icelandic
        'it': 'it',  # Italian
        'fr': 'fr',  # French
        'es': 'es',  # Spanish
        'pt': 'pt',  # Portuguese
        'ro': 'ro',  # Romanian
        'ca': 'ca',  # Catalan
        'ga': 'ga',  # Irish
        'cy': 'cy',  # Welsh
        'gd': 'gd',  # Scottish Gaelic
        'en': 'en',  # English
        'el': 'el',  # Greek
        'hi': 'hi',  # Hindi
        'fa': 'fa',  # Persian
        'lt': 'lt',  # Lithuanian
        'lv': 'lv',  # Latvian
        'et': 'et',  # Estonian
        'hu': 'hu',  # Hungarian
        'fi': 'fi',  # Finnish
    }
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize Google Translate provider.
        
        Args:
            api_key: Google Cloud API key (optional if using service account)
            **kwargs: Additional configuration options
        """
        super().__init__(api_key, **kwargs)
        
        if not GOOGLE_AVAILABLE:
            raise ProviderUnavailableError(
                "Google Cloud Translate library not available. Install with: pip install google-cloud-translate",
                provider="google"
            )
        
        # Initialize the client
        try:
            if api_key:
                # Use API key authentication
                import os
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = api_key
                self.client = translate.Client()
            else:
                # Try default credentials, fallback to anonymous
                try:
                    self.client = translate.Client()
                except Exception:
                    # Try with anonymous access (limited)
                    self.client = translate.Client()
                
            self._supported_languages = None
            self._last_request_time = 0
            self._rate_limit_delay = 0.1  # 100ms between requests
            
        except Exception as e:
            raise ProviderUnavailableError(
                f"Failed to initialize Google Translate client: {str(e)}",
                provider="google"
            )
    
    def _map_language_code(self, lang_code: str) -> str:
        """Map our language codes to Google's language codes."""
        return self.LANGUAGE_MAPPING.get(lang_code, lang_code)
    
    def _reverse_map_language_code(self, google_code: str) -> str:
        """Map Google's language codes back to our standard codes."""
        reverse_mapping = {v: k for k, v in self.LANGUAGE_MAPPING.items()}
        return reverse_mapping.get(google_code, google_code)
    
    async def _rate_limit(self):
        """Implement basic rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        self._last_request_time = time.time()
    
    async def translate(
        self, 
        text: str, 
        target_language: str, 
        source_language: Optional[str] = None
    ) -> TranslationResult:
        """
        Translate text using Google Translate.
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code (auto-detect if None)
            
        Returns:
            TranslationResult with translated text and metadata
        """
        if not text.strip():
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language or 'unknown',
                target_language=target_language,
                confidence_score=0.0,
                provider='google'
            )
        
        try:
            await self._rate_limit()
            start_time = time.time()
            
            # Map language codes
            google_target = self._map_language_code(target_language)
            google_source = self._map_language_code(source_language) if source_language else None
            
            # Perform translation
            result = self.client.translate(
                text,
                target_language=google_target,
                source_language=google_source
            )
            
            processing_time = time.time() - start_time
            
            # Extract results
            translated_text = result['translatedText']
            detected_source = self._reverse_map_language_code(result.get('detectedSourceLanguage', source_language or 'unknown'))
            
            # Google doesn't provide confidence scores, so we estimate based on factors
            confidence_score = self._estimate_confidence(text, translated_text, detected_source, target_language)
            
            self.logger.info(
                "Translation completed",
                source_lang=detected_source,
                target_lang=target_language,
                char_count=len(text),
                processing_time=processing_time
            )
            
            return TranslationResult(
                original_text=text,
                translated_text=translated_text,
                source_language=detected_source,
                target_language=target_language,
                confidence_score=confidence_score,
                provider='google',
                processing_time=processing_time,
                character_count=len(text)
            )
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if 'quota' in error_msg or 'rate limit' in error_msg or 'too many requests' in error_msg:
                raise RateLimitError(f"Google Translate rate limit exceeded: {str(e)}", provider="google")
            elif 'unsupported' in error_msg or 'invalid language' in error_msg:
                raise UnsupportedLanguageError(f"Language pair not supported: {source_language} -> {target_language}", provider="google")
            else:
                raise TranslationError(f"Google Translate API error: {str(e)}", provider="google")
    
    def _estimate_confidence(self, original: str, translated: str, source_lang: str, target_lang: str) -> float:
        """
        Estimate translation confidence based on various factors.
        Google doesn't provide confidence scores, so we estimate.
        """
        confidence = 0.8  # Base confidence for Google Translate
        
        # Adjust based on text length (longer texts generally more reliable)
        if len(original) > 100:
            confidence += 0.1
        elif len(original) < 10:
            confidence -= 0.2
        
        # Adjust if source and target are the same (no translation needed)
        if source_lang == target_lang:
            confidence = 1.0
        
        # Adjust if translated text is identical (might indicate no translation occurred)
        elif original.strip() == translated.strip():
            confidence *= 0.5
        
        # Adjust based on language pair (Google is generally strong for major languages)
        major_languages = {'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko'}
        if source_lang in major_languages and target_lang in major_languages:
            confidence += 0.1
        
        return min(1.0, max(0.0, confidence))
    
    async def detect_language(self, text: str) -> LanguageDetectionResult:
        """
        Detect the language of input text.
        
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
                provider='google'
            )
        
        try:
            await self._rate_limit()
            
            result = self.client.detect_language(text)
            
            # Google returns a list of detection results
            if isinstance(result, list) and result:
                detection = result[0]
            else:
                detection = result
            
            detected_lang = self._reverse_map_language_code(detection['language'])
            confidence = detection.get('confidence', 0.0)
            
            # Prepare alternative languages if available
            alternatives = []
            if isinstance(result, list) and len(result) > 1:
                for alt in result[1:5]:  # Top 5 alternatives
                    alt_lang = self._reverse_map_language_code(alt['language'])
                    alt_conf = alt.get('confidence', 0.0)
                    alternatives.append({alt_lang: alt_conf})
            
            self.logger.info(
                "Language detected",
                language=detected_lang,
                confidence=confidence,
                char_count=len(text)
            )
            
            return LanguageDetectionResult(
                text=text,
                detected_language=detected_lang,
                confidence_score=confidence,
                provider='google',
                alternative_languages=alternatives
            )
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if 'quota' in error_msg or 'rate limit' in error_msg:
                raise RateLimitError(f"Google Translate rate limit exceeded: {str(e)}", provider="google")
            else:
                raise TranslationError(f"Google language detection error: {str(e)}", provider="google")
    
    async def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        if self._supported_languages is not None:
            return self._supported_languages
        
        try:
            await self._rate_limit()
            
            languages = self.client.get_languages()
            
            # Convert Google's language codes to our standard codes
            supported = []
            for lang in languages:
                standard_code = self._reverse_map_language_code(lang['language'])
                if standard_code in self.LANGUAGE_MAPPING:
                    supported.append(standard_code)
            
            self._supported_languages = supported
            
            self.logger.info("Retrieved supported languages", count=len(supported))
            
            return supported
            
        except Exception as e:
            self.logger.error("Failed to get supported languages", error=str(e))
            # Return our known supported languages as fallback
            return list(self.LANGUAGE_MAPPING.keys())
    
    def get_provider_name(self) -> str:
        """Get provider name for identification."""
        return "Google Translate"
    
    async def translate_batch(
        self, 
        texts: List[str], 
        target_language: str, 
        source_language: Optional[str] = None
    ) -> List[TranslationResult]:
        """
        Translate multiple texts efficiently using batch API.
        
        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Source language code (auto-detect if None)
            
        Returns:
            List of TranslationResult objects
        """
        if not texts:
            return []
        
        try:
            await self._rate_limit()
            start_time = time.time()
            
            # Map language codes
            google_target = self._map_language_code(target_language)
            google_source = self._map_language_code(source_language) if source_language else None
            
            # Perform batch translation
            results = self.client.translate(
                texts,
                target_language=google_target,
                source_language=google_source
            )
            
            processing_time = time.time() - start_time
            
            # Process results
            translation_results = []
            for i, (original_text, result) in enumerate(zip(texts, results)):
                translated_text = result['translatedText']
                detected_source = self._reverse_map_language_code(
                    result.get('detectedSourceLanguage', source_language or 'unknown')
                )
                
                confidence_score = self._estimate_confidence(
                    original_text, translated_text, detected_source, target_language
                )
                
                translation_results.append(TranslationResult(
                    original_text=original_text,
                    translated_text=translated_text,
                    source_language=detected_source,
                    target_language=target_language,
                    confidence_score=confidence_score,
                    provider='google',
                    processing_time=processing_time / len(texts),  # Distribute time across all translations
                    character_count=len(original_text)
                ))
            
            self.logger.info(
                "Batch translation completed",
                batch_size=len(texts),
                total_processing_time=processing_time
            )
            
            return translation_results
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if 'quota' in error_msg or 'rate limit' in error_msg:
                raise RateLimitError(f"Google Translate rate limit exceeded: {str(e)}", provider="google")
            else:
                # Fall back to individual translations
                self.logger.warning("Batch translation failed, falling back to individual translations", error=str(e))
                return await super().translate_batch(texts, target_language, source_language)