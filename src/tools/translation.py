"""
Multi-provider translation tool for international research capabilities.
"""

import asyncio
import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class TranslationResult:
    """Result of translation operation with metadata."""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence_score: float
    provider: str
    processing_time: float = 0.0
    character_count: int = 0
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.character_count == 0:
            self.character_count = len(self.original_text)


@dataclass
class LanguageDetectionResult:
    """Result of language detection operation."""
    text: str
    detected_language: str
    confidence_score: float
    provider: str
    alternative_languages: List[Dict[str, float]] = None
    
    def __post_init__(self):
        if self.alternative_languages is None:
            self.alternative_languages = []


class TranslationProvider(ABC):
    """Abstract base class for translation service providers."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.config = kwargs
        self.logger = logger.bind(provider=self.__class__.__name__)
    
    @abstractmethod
    async def translate(
        self, 
        text: str, 
        target_language: str, 
        source_language: Optional[str] = None
    ) -> TranslationResult:
        """
        Translate text from source to target language.
        
        Args:
            text: Text to translate
            target_language: Target language code (ISO 639-1)
            source_language: Source language code (auto-detect if None)
            
        Returns:
            TranslationResult with translated text and metadata
        """
        pass
    
    @abstractmethod
    async def detect_language(self, text: str) -> LanguageDetectionResult:
        """
        Detect the language of input text.
        
        Args:
            text: Text to analyze
            
        Returns:
            LanguageDetectionResult with detected language and confidence
        """
        pass
    
    @abstractmethod
    async def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name for identification."""
        pass
    
    @abstractmethod
    async def translate_batch(
        self, 
        texts: List[str], 
        target_language: str, 
        source_language: Optional[str] = None
    ) -> List[TranslationResult]:
        """
        Translate multiple texts efficiently.
        
        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Source language code (auto-detect if None)
            
        Returns:
            List of TranslationResult objects
        """
        # Default implementation - can be overridden for batch optimization
        results = []
        for text in texts:
            result = await self.translate(text, target_language, source_language)
            results.append(result)
        return results


class TranslationError(Exception):
    """Base exception for translation errors."""
    
    def __init__(self, message: str, provider: str = None, error_code: str = None):
        self.message = message
        self.provider = provider
        self.error_code = error_code
        super().__init__(self.message)


class ProviderUnavailableError(TranslationError):
    """Raised when translation provider is unavailable."""
    pass


class RateLimitError(TranslationError):
    """Raised when translation provider rate limit is exceeded."""
    pass


class UnsupportedLanguageError(TranslationError):
    """Raised when language pair is not supported by provider."""
    pass


class TranslationTool:
    """
    Multi-provider translation service with failover and caching.
    
    Provides translation capabilities with multiple backend providers,
    automatic failover, caching, and language detection.
    """
    
    # Supported language codes with display names
    SUPPORTED_LANGUAGES = {
        # Slavic Languages
        'sl': 'Slovenian',
        'hr': 'Croatian', 
        'sr': 'Serbian',
        'cs': 'Czech',
        'pl': 'Polish',
        'ru': 'Russian',
        'sk': 'Slovak',
        'bg': 'Bulgarian',
        
        # Germanic Languages  
        'de': 'German',
        'nl': 'Dutch',
        'sv': 'Swedish',
        'no': 'Norwegian',
        'da': 'Danish',
        'is': 'Icelandic',
        
        # Romance Languages
        'it': 'Italian',
        'fr': 'French', 
        'es': 'Spanish',
        'pt': 'Portuguese',
        'ro': 'Romanian',
        'ca': 'Catalan',
        
        # Celtic Languages
        'ga': 'Irish',
        'cy': 'Welsh',
        'gd': 'Scottish Gaelic',
        
        # Other Indo-European
        'en': 'English',
        'el': 'Greek',
        'hi': 'Hindi',
        'fa': 'Persian',
        'lt': 'Lithuanian',
        'lv': 'Latvian',
        'et': 'Estonian',
        'hu': 'Hungarian',
        'fi': 'Finnish'
    }
    
    # Provider priority by language pair (source-target)
    PROVIDER_PREFERENCES = {
        # European languages - prefer DeepL
        ('en', 'de'): ['deepl', 'google', 'azure'],
        ('en', 'fr'): ['deepl', 'google', 'azure'],
        ('en', 'es'): ['deepl', 'google', 'azure'],
        ('en', 'it'): ['deepl', 'google', 'azure'],
        ('en', 'sl'): ['deepl', 'google', 'azure'],
        ('en', 'nl'): ['deepl', 'google', 'azure'],
        ('en', 'pl'): ['deepl', 'google', 'azure'],
        ('en', 'cs'): ['deepl', 'google', 'azure'],
        
        # Reverse direction
        ('de', 'en'): ['deepl', 'google', 'azure'],
        ('fr', 'en'): ['deepl', 'google', 'azure'],
        ('es', 'en'): ['deepl', 'google', 'azure'],
        ('it', 'en'): ['deepl', 'google', 'azure'],
        ('sl', 'en'): ['deepl', 'google', 'azure'],
        
        # Default preference for other pairs
        'default': ['llm', 'google', 'deepl', 'azure', 'mock']
    }
    
    def __init__(
        self, 
        default_provider: str = 'llm',
        enable_cache: bool = True,
        cache_ttl_hours: int = 720,
        llm_client=None,
    ):
        """
        Initialize translation tool.
        
        Args:
            default_provider: Default translation provider
            enable_cache: Enable translation caching
            cache_ttl_hours: Cache time-to-live in hours
            llm_client: LLM client for LLM-based translation (recommended)
        """
        self.providers = {}
        self.default_provider = default_provider
        self.enable_cache = enable_cache
        self.cache_ttl_hours = cache_ttl_hours
        self.llm_client = llm_client
        self.logger = logger.bind(component="translation_tool")
        
        # Initialize providers (will be implemented in separate methods)
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available translation providers."""
        self.providers = {}
        
        # Try LLM provider first (best quality, uses existing API keys)
        if self.llm_client:
            try:
                from .providers.llm_translate import LLMTranslateProvider
                llm_provider = LLMTranslateProvider(llm_client=self.llm_client)
                self.providers['llm'] = llm_provider
                self.logger.info("LLM translation provider initialized")
            except Exception as e:
                self.logger.warning("Failed to initialize LLM translation provider", error=str(e))
        
        # Try Google Translate as fallback
        try:
            from .providers import GoogleTranslateProvider
            google_provider = GoogleTranslateProvider()
            self.providers['google'] = google_provider
            self.logger.info("Google Translate provider initialized")
        except Exception as e:
            self.logger.warning("Failed to initialize Google Translate provider", error=str(e))
        
        # Mock provider as last resort
        if not self.providers:
            try:
                from .providers.mock_translate import MockTranslateProvider
                mock_provider = MockTranslateProvider()
                self.providers['mock'] = mock_provider
                self.logger.info("Mock translation provider initialized as fallback")
            except Exception as mock_error:
                self.logger.warning("Failed to initialize mock provider", error=str(mock_error))
        
        # Initialize fallback language detector
        try:
            from .language_detection import LanguageDetector
            self.language_detector = LanguageDetector()
            self.logger.info("Fallback language detector initialized")
        except Exception as e:
            self.logger.warning("Failed to initialize language detector", error=str(e))
            self.language_detector = None
        
        # Initialize translation cache if enabled
        if self.enable_cache:
            try:
                from .translation_cache import TranslationCache
                self.cache = TranslationCache(ttl_hours=self.cache_ttl_hours)
                self.logger.info("Translation cache initialized")
            except Exception as e:
                self.logger.warning("Failed to initialize translation cache", error=str(e))
                self.cache = None
                self.enable_cache = False
        else:
            self.cache = None
        
        self.logger.info("Translation providers initialized", count=len(self.providers))
    
    def register_provider(self, name: str, provider: TranslationProvider):
        """Register a translation provider."""
        self.providers[name] = provider
        self.logger.info("Translation provider registered", provider=name)
    
    def get_provider_priority(self, source_lang: str, target_lang: str) -> List[str]:
        """
        Get provider priority order for language pair.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            List of provider names in priority order
        """
        # Check specific language pair preferences
        lang_pair = (source_lang, target_lang)
        if lang_pair in self.PROVIDER_PREFERENCES:
            providers = self.PROVIDER_PREFERENCES[lang_pair].copy()
        else:
            providers = self.PROVIDER_PREFERENCES['default'].copy()
        
        # Filter to only available providers
        available_providers = [p for p in providers if p in self.providers]
        
        # Add any remaining providers
        for provider_name in self.providers:
            if provider_name not in available_providers:
                available_providers.append(provider_name)
        
        return available_providers
    
    def _generate_cache_key(self, text: str, target_lang: str, source_lang: str) -> str:
        """Generate cache key for translation."""
        cache_string = f"{source_lang}:{target_lang}:{text}"
        return hashlib.md5(cache_string.encode('utf-8')).hexdigest()
    
    async def detect_language(self, text: str, provider: Optional[str] = None) -> LanguageDetectionResult:
        """
        Detect language of input text.
        
        Args:
            text: Text to analyze
            provider: Specific provider to use (optional)
            
        Returns:
            LanguageDetectionResult with detected language
        """
        if not text.strip():
            return LanguageDetectionResult(
                text=text,
                detected_language='unknown',
                confidence_score=0.0,
                provider='none'
            )
        
        # Try specified provider first, then fallback
        providers_to_try = [provider] if provider and provider in self.providers else list(self.providers.keys())
        
        for provider_name in providers_to_try:
            try:
                provider_instance = self.providers[provider_name]
                result = await provider_instance.detect_language(text)
                self.logger.info(
                    "Language detected",
                    provider=provider_name,
                    language=result.detected_language,
                    confidence=result.confidence_score
                )
                return result
                
            except Exception as e:
                self.logger.warning(
                    "Language detection failed",
                    provider=provider_name,
                    error=str(e)
                )
                continue
        
        # Try fallback language detector if available
        if hasattr(self, 'language_detector') and self.language_detector:
            try:
                result = await self.language_detector.detect_language(text)
                self.logger.info(
                    "Language detected using fallback",
                    language=result.detected_language,
                    confidence=result.confidence_score
                )
                return result
            except Exception as e:
                self.logger.warning("Fallback language detection failed", error=str(e))
        
        # All providers failed
        raise TranslationError("All language detection providers failed")
    
    async def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
        provider: Optional[str] = None
    ) -> TranslationResult:
        """
        Translate text with automatic provider selection and failover.
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code (auto-detect if None)
            provider: Specific provider to use (optional)
            
        Returns:
            TranslationResult with translated text
        """
        if not text.strip():
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language or 'unknown',
                target_language=target_language,
                confidence_score=0.0,
                provider='none'
            )
        
        # Auto-detect source language if not provided
        if source_language is None:
            detection_result = await self.detect_language(text)
            source_language = detection_result.detected_language
        
        # Return original if same language
        if source_language == target_language:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
                confidence_score=1.0,
                provider='none'
            )
        
        # Check cache if enabled
        if self.enable_cache and self.cache:
            cached_result = await self.cache.get_translation(text, target_language, source_language)
            if cached_result:
                self.logger.info("Translation retrieved from cache", 
                               source_lang=source_language, target_lang=target_language)
                return cached_result
        
        # Get provider priority order
        if provider and provider in self.providers:
            providers_to_try = [provider]
        else:
            providers_to_try = self.get_provider_priority(source_language, target_language)
        
        # Try providers in order
        for provider_name in providers_to_try:
            try:
                provider_instance = self.providers[provider_name]
                start_time = asyncio.get_event_loop().time()
                
                result = await provider_instance.translate(text, target_language, source_language)
                
                processing_time = asyncio.get_event_loop().time() - start_time
                result.processing_time = processing_time
                
                # Cache result if enabled
                if self.enable_cache and self.cache:
                    await self.cache.store_translation(result, provider_name)
                
                self.logger.info(
                    "Translation completed",
                    provider=provider_name,
                    source_lang=source_language,
                    target_lang=target_language,
                    char_count=len(text),
                    processing_time=processing_time
                )
                
                return result
                
            except UnsupportedLanguageError:
                self.logger.warning(
                    "Language pair not supported",
                    provider=provider_name,
                    source_lang=source_language,
                    target_lang=target_language
                )
                continue
                
            except (ProviderUnavailableError, RateLimitError) as e:
                self.logger.warning(
                    "Provider unavailable, trying next",
                    provider=provider_name,
                    error=str(e)
                )
                continue
                
            except Exception as e:
                self.logger.error(
                    "Translation failed",
                    provider=provider_name,
                    error=str(e)
                )
                continue
        
        # All providers failed - return original with warning
        self.logger.error(
            "All translation providers failed",
            source_lang=source_language,
            target_lang=target_language
        )
        
        return TranslationResult(
            original_text=text,
            translated_text=text,
            source_language=source_language,
            target_language=target_language,
            confidence_score=0.0,
            provider='fallback'
        )
    
    async def translate_batch(
        self,
        texts: List[str],
        target_language: str,
        source_language: Optional[str] = None,
        provider: Optional[str] = None
    ) -> List[TranslationResult]:
        """
        Translate multiple texts efficiently.
        
        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Source language code (auto-detect if None)
            provider: Specific provider to use (optional)
            
        Returns:
            List of TranslationResult objects
        """
        if not texts:
            return []
        
        # For now, translate sequentially - can be optimized later
        results = []
        for text in texts:
            result = await self.translate(text, target_language, source_language, provider)
            results.append(result)
        
        return results
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get supported language codes and names."""
        return self.SUPPORTED_LANGUAGES.copy()
    
    def is_language_supported(self, language_code: str) -> bool:
        """Check if language is supported."""
        return language_code in self.SUPPORTED_LANGUAGES
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self.providers.keys())
    
    async def get_provider_info(self, provider_name: str) -> Dict[str, Any]:
        """Get information about a specific provider."""
        if provider_name not in self.providers:
            raise ValueError(f"Provider {provider_name} not available")
        
        provider = self.providers[provider_name]
        
        try:
            supported_langs = await provider.get_supported_languages()
            return {
                'name': provider.get_provider_name(),
                'supported_languages': supported_langs,
                'available': True
            }
        except Exception as e:
            return {
                'name': provider.get_provider_name(),
                'supported_languages': [],
                'available': False,
                'error': str(e)
            }