"""
LLM-based translation provider using existing OpenAI/Anthropic/DeepSeek clients.
"""

import asyncio
import time
from typing import List, Optional
import structlog

from ..translation import (
    TranslationProvider,
    TranslationResult,
    LanguageDetectionResult,
    TranslationError,
)

logger = structlog.get_logger()

# Language code to full name mapping
LANGUAGE_NAMES = {
    "en": "English", "de": "German", "fr": "French", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
    "pl": "Polish", "cs": "Czech", "sl": "Slovenian", "hr": "Croatian",
    "sr": "Serbian", "sk": "Slovak", "bg": "Bulgarian", "ro": "Romanian",
    "sv": "Swedish", "no": "Norwegian", "da": "Danish", "el": "Greek",
    "hi": "Hindi", "fa": "Persian", "mk": "Macedonian", "hu": "Hungarian",
    "fi": "Finnish", "et": "Estonian", "lv": "Latvian", "lt": "Lithuanian",
    "ca": "Catalan", "ga": "Irish", "cy": "Welsh", "is": "Icelandic",
}


class LLMTranslateProvider(TranslationProvider):
    """
    Translation provider that uses an LLM client for high-quality translations.

    Works with any LLM client that implements the generate(system_prompt, user_message) interface
    (OpenAI, Anthropic, DeepSeek, or the ImprovedLLMClient with fallback chains).
    """

    def __init__(self, llm_client, **kwargs):
        """
        Args:
            llm_client: Any LLM client with an async generate() method.
        """
        super().__init__(**kwargs)
        self.llm_client = llm_client
        self.logger = logger.bind(provider="llm_translate")

    def get_provider_name(self) -> str:
        return "llm"

    async def get_supported_languages(self) -> List[str]:
        return list(LANGUAGE_NAMES.keys())

    async def detect_language(self, text: str) -> LanguageDetectionResult:
        """Detect language using the LLM."""
        prompt = (
            "Detect the language of the following text. "
            "Reply with ONLY the ISO 639-1 two-letter language code (e.g. en, de, fr). "
            "Nothing else."
        )
        try:
            response = await self.llm_client.generate(
                system_prompt=prompt,
                user_message=text[:500],  # limit input size
                temperature=0.0,
                max_tokens=5,
            )
            code = response.strip().lower()[:2]
            return LanguageDetectionResult(
                text=text,
                detected_language=code,
                confidence_score=0.9,
                provider="llm",
            )
        except Exception as e:
            self.logger.error("LLM language detection failed", error=str(e))
            return LanguageDetectionResult(
                text=text,
                detected_language="en",
                confidence_score=0.0,
                provider="llm",
            )

    async def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> TranslationResult:
        """Translate text using the LLM."""
        source_name = LANGUAGE_NAMES.get(source_language, source_language or "auto-detected")
        target_name = LANGUAGE_NAMES.get(target_language, target_language)

        system_prompt = (
            f"You are a professional translator. "
            f"Translate the following text from {source_name} to {target_name}. "
            f"Preserve all formatting (markdown, headers, lists, bold, etc.). "
            f"Do NOT add any commentary, notes, or explanations. "
            f"Output ONLY the translated text."
        )

        start = time.time()
        try:
            translated = await self.llm_client.generate(
                system_prompt=system_prompt,
                user_message=text,
                temperature=0.3,
            )
            elapsed = time.time() - start

            return TranslationResult(
                original_text=text,
                translated_text=translated.strip(),
                source_language=source_language or "auto",
                target_language=target_language,
                confidence_score=0.95,
                provider="llm",
                processing_time=elapsed,
                character_count=len(text),
            )
        except Exception as e:
            self.logger.error("LLM translation failed", error=str(e))
            raise TranslationError(
                message=f"LLM translation failed: {e}",
                provider="llm",
            )

    async def translate_batch(
        self,
        texts: List[str],
        target_language: str,
        source_language: Optional[str] = None,
    ) -> List[TranslationResult]:
        """Translate multiple texts. Runs sequentially to respect rate limits."""
        results = []
        for text in texts:
            result = await self.translate(text, target_language, source_language)
            results.append(result)
        return results
