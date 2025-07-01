from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import openai
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

logger = structlog.get_logger()


def normalize_text(text: str) -> str:
    """Normalize text to handle Unicode encoding issues."""
    if not text:
        return ""
    
    try:
        # Handle case where text might have encoding issues
        if isinstance(text, str):
            # Try to encode and decode to clean up any encoding issues
            normalized = text.encode('utf-8', errors='replace').decode('utf-8')
            return normalized
        return str(text)
    except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
        # If all else fails, replace problematic characters
        return str(text).encode('ascii', errors='replace').decode('ascii')


class LLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        pass


class OpenAIClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: Optional[str] = None
    ):
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        try:
            # Normalize input text to handle Unicode issues
            normalized_system = normalize_text(system_prompt)
            normalized_user = normalize_text(user_message)
            
            messages = [
                {"role": "system", "content": normalized_system},
                {"role": "user", "content": normalized_user}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            content = response.choices[0].message.content
            return normalize_text(content) if content else ""
            
        except Exception as e:
            logger.error("OpenAI API call failed", error=str(e))
            raise


class AnthropicClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229"
    ):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        try:
            # Normalize input text to handle Unicode issues
            normalized_system = normalize_text(system_prompt)
            normalized_user = normalize_text(user_message)
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or 1000,
                temperature=temperature,
                system=normalized_system,
                messages=[
                    {"role": "user", "content": normalized_user}
                ],
                **kwargs
            )
            
            content = response.content[0].text
            return normalize_text(content) if content else ""
            
        except Exception as e:
            logger.error("Anthropic API call failed", error=str(e))
            raise


def create_llm_client(provider: str, **kwargs) -> LLMClient:
    if provider.lower() == "openai":
        return OpenAIClient(**kwargs)
    elif provider.lower() == "anthropic":
        return AnthropicClient(**kwargs)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")