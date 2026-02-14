#!/usr/bin/env python3
"""
Improved Rate Limiting and Error Handling for AI Research Assistant
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncGenerator, Callable
import openai
import anthropic
from openai import AsyncOpenAI  # For DeepSeek compatibility
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog

logger = structlog.get_logger()


class RateLimitManager:
    """Manages API rate limits and request queuing."""
    
    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 3500):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_requests = []
        self.hour_requests = []
        self.lock = asyncio.Lock()
    
    async def wait_if_needed(self):
        """Wait if we're approaching rate limits."""
        async with self.lock:
            now = time.time()
            
            # Clean old requests
            minute_ago = now - 60
            hour_ago = now - 3600
            
            self.minute_requests = [t for t in self.minute_requests if t > minute_ago]
            self.hour_requests = [t for t in self.hour_requests if t > hour_ago]
            
            # Check if we need to wait
            if len(self.minute_requests) >= self.requests_per_minute:
                wait_time = 60 - (now - self.minute_requests[0])
                if wait_time > 0:
                    logger.info(f"Rate limiting: waiting {wait_time:.1f}s for minute limit")
                    await asyncio.sleep(wait_time)
            
            if len(self.hour_requests) >= self.requests_per_hour:
                wait_time = 3600 - (now - self.hour_requests[0])
                if wait_time > 0:
                    logger.info(f"Rate limiting: waiting {wait_time:.1f}s for hour limit")
                    await asyncio.sleep(wait_time)
            
            # Record this request
            current_time = time.time()
            self.minute_requests.append(current_time)
            self.hour_requests.append(current_time)


class ImprovedLLMClient(ABC):
    """Enhanced LLM client with better error handling and rate limiting."""
    
    def __init__(self):
        self.rate_limiter = RateLimitManager()
        self.fallback_client = None
    
    def set_fallback(self, fallback_client: 'ImprovedLLMClient'):
        """Set a fallback client for when primary fails."""
        self.fallback_client = fallback_client
    
    def set_fallback_chain(self, fallback_clients: List['ImprovedLLMClient']):
        """Set a chain of fallback clients."""
        if not fallback_clients:
            return
        
        # Set up the chain: primary -> fallback1 -> fallback2 -> ...
        current = self
        for fallback in fallback_clients:
            current.fallback_client = fallback
            current = fallback
    
    @abstractmethod
    async def _generate_internal(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Internal generation method to be implemented by subclasses."""
        pass
    
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        use_fallback: bool = True,
        **kwargs
    ) -> str:
        """Generate text with rate limiting and fallback support."""
        
        try:
            # Wait for rate limiting
            await self.rate_limiter.wait_if_needed()
            
            # Try primary generation
            return await self._generate_internal(
                system_prompt, user_message, max_tokens, temperature, **kwargs
            )
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for quota/rate limit errors (including tenacity RetryError)
            is_quota_error = any(term in error_msg for term in [
                'quota', 'rate limit', '429', 'insufficient_quota', 
                'insufficient balance', '402', 'billing', 'limit exceeded',
                'authentication_error', 'invalid x-api-key', '401'
            ])
            
            # Also check if it's a tenacity RetryError wrapping a rate limit error
            is_retry_error = False
            if hasattr(e, 'last_attempt') and e.last_attempt:
                if hasattr(e.last_attempt, 'exception') and e.last_attempt.exception:
                    inner_error = str(e.last_attempt.exception()).lower()
                    is_retry_error = any(term in inner_error for term in [
                        'quota', 'rate limit', '429', 'insufficient_quota',
                        'insufficient balance', '402', 'billing', 'limit exceeded',
                        'authentication_error', 'invalid x-api-key', '401'
                    ])
            
            if is_quota_error or is_retry_error:
                logger.warning(f"Primary API quota/rate limit exceeded: {e}")
                
                if use_fallback and self.fallback_client:
                    logger.info("Attempting fallback API")
                    return await self.fallback_client.generate(
                        system_prompt, user_message, max_tokens, temperature, 
                        use_fallback=True, **kwargs  # Changed to True to allow chaining
                    )
                else:
                    # No fallback available - implement graceful degradation
                    return await self._graceful_degradation(system_prompt, user_message)
            
            # For other errors, re-raise
            logger.error(f"LLM generation failed: {e}")
            raise


    async def _graceful_degradation(self, system_prompt: str, user_message: str) -> str:
        """Provide a graceful fallback when APIs are unavailable."""
        return f"""
        [AI Research Assistant - Service Temporarily Unavailable]
        
        We're experiencing high demand and have temporarily exceeded our API quotas.
        
        Your research topic: {user_message[:100]}...
        
        Please try again in a few minutes, or consider:
        1. Breaking down your research into smaller, more specific topics
        2. Trying again during off-peak hours
        3. Using fewer research queries per session
        
        We apologize for the inconvenience and are working to increase our capacity.
        """

    @abstractmethod
    async def _stream_internal(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Internal streaming method to be implemented by subclasses."""
        pass
        yield  # Make it a generator

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        on_chunk: Optional[Callable[[str, str], None]] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        use_fallback: bool = True,
        **kwargs
    ) -> str:
        """
        Generate text with streaming, calling on_chunk(new_text, full_text_so_far) 
        as tokens arrive. Returns the complete text.
        
        Args:
            on_chunk: callback(chunk, accumulated_text) called as tokens arrive
        """
        try:
            await self.rate_limiter.wait_if_needed()
            
            accumulated = []
            async for chunk in self._stream_internal(
                system_prompt, user_message, max_tokens, temperature, **kwargs
            ):
                accumulated.append(chunk)
                if on_chunk:
                    try:
                        on_chunk(chunk, ''.join(accumulated))
                    except Exception:
                        pass  # Don't let callback errors kill the stream
            
            return ''.join(accumulated)
            
        except Exception as e:
            error_msg = str(e).lower()
            is_quota_error = any(term in error_msg for term in [
                'quota', 'rate limit', '429', 'insufficient_quota',
                'insufficient balance', '402', 'billing', 'limit exceeded',
                'authentication_error', 'invalid x-api-key', '401'
            ])
            
            if is_quota_error and use_fallback and self.fallback_client:
                logger.warning(f"Primary stream failed, trying fallback: {e}")
                return await self.fallback_client.generate_stream(
                    system_prompt, user_message, on_chunk,
                    max_tokens, temperature, use_fallback=True, **kwargs
                )
            
            logger.error(f"LLM stream failed: {e}")
            raise


class ImprovedOpenAIClient(ImprovedLLMClient):
    """Enhanced OpenAI client with improved error handling."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        super().__init__()
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        # More conservative rate limiting for OpenAI
        self.rate_limiter = RateLimitManager(requests_per_minute=20, requests_per_hour=1000)
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60)  # More aggressive backoff
    )
    async def _generate_internal(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            content = response.choices[0].message.content
            return content if content else ""
            
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenAI unexpected error: {e}")
            raise

    async def _stream_internal(
        self, system_prompt, user_message, max_tokens=None, temperature=0.7, **kwargs
    ) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class ImprovedDeepSeekClient(ImprovedLLMClient):
    """Enhanced DeepSeek client with improved error handling."""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__()
        # DeepSeek uses OpenAI-compatible API
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = model
        # DeepSeek has generous rate limits and low costs
        self.rate_limiter = RateLimitManager(requests_per_minute=100, requests_per_hour=5000)
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60)
    )
    async def _generate_internal(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            content = response.choices[0].message.content
            return content if content else ""
            
        except openai.RateLimitError as e:
            logger.error(f"DeepSeek rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"DeepSeek API error: {e}")
            raise
        except Exception as e:
            logger.error(f"DeepSeek unexpected error: {e}")
            raise

    async def _stream_internal(
        self, system_prompt, user_message, max_tokens=None, temperature=0.7, **kwargs
    ) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class ImprovedAnthropicClient(ImprovedLLMClient):
    """Enhanced Anthropic client with improved error handling."""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        super().__init__()
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        # Anthropic has different rate limits
        self.rate_limiter = RateLimitManager(requests_per_minute=50, requests_per_hour=2000)
    
    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APITimeoutError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60)
    )
    async def _generate_internal(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or 1000,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                **kwargs
            )
            
            content = response.content[0].text
            return content if content else ""
            
        except anthropic.RateLimitError as e:
            logger.error(f"Anthropic rate limit exceeded: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Anthropic unexpected error: {e}")
            raise

    async def _stream_internal(
        self, system_prompt, user_message, max_tokens=None, temperature=0.7, **kwargs
    ) -> AsyncGenerator[str, None]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens or 4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text


class ResearchRequestQueue:
    """Queue system to prevent overwhelming APIs with concurrent requests."""
    
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_requests = 0
        self.lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        async with self.lock:
            self.active_requests += 1
            logger.info(f"Starting research request ({self.active_requests}/{self.max_concurrent} active)")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self.lock:
            self.active_requests -= 1
            logger.info(f"Completed research request ({self.active_requests}/{self.max_concurrent} active)")
        self.semaphore.release()


def create_improved_llm_client(
    primary_provider: str,
    fallback_provider: Optional[str] = None,
    final_fallback_provider: Optional[str] = None,
    **kwargs
) -> ImprovedLLMClient:
    """
    Create an improved LLM client with multi-tier fallback support.
    
    Args:
        primary_provider: "openai", "anthropic", or "deepseek"
        fallback_provider: Optional first fallback provider
        final_fallback_provider: Optional final fallback provider
        **kwargs: API keys and other config
    
    Returns:
        Configured LLM client with fallback chain
    """
    
    def _create_client(provider: str):
        """Helper to create client for any provider."""
        if provider.lower() == "openai":
            return ImprovedOpenAIClient(
                api_key=kwargs.get('openai_api_key'),
                model=kwargs.get('openai_model', 'gpt-4')
            )
        elif provider.lower() == "anthropic":
            return ImprovedAnthropicClient(
                api_key=kwargs.get('anthropic_api_key'),
                model=kwargs.get('anthropic_model', 'claude-3-sonnet-20240229')
            )
        elif provider.lower() == "deepseek":
            return ImprovedDeepSeekClient(
                api_key=kwargs.get('deepseek_api_key'),
                model=kwargs.get('deepseek_model', 'deepseek-chat')
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    # Create primary client
    primary = _create_client(primary_provider)
    
    # Build fallback chain
    fallback_clients = []
    
    if fallback_provider:
        fallback_clients.append(_create_client(fallback_provider))
    
    if final_fallback_provider:
        fallback_clients.append(_create_client(final_fallback_provider))
    
    # Set up the fallback chain
    if fallback_clients:
        primary.set_fallback_chain(fallback_clients)
    
    return primary


# Global request queue
research_queue = ResearchRequestQueue(max_concurrent=2)


if __name__ == "__main__":
    """Example usage of improved rate limiting."""
    
    async def test_improved_client():
        # Example configuration
        client = create_improved_llm_client(
            primary_provider="openai",
            fallback_provider="anthropic",
            openai_api_key="your-openai-key",
            anthropic_api_key="your-anthropic-key"
        )
        
        # Test with rate limiting and fallback
        async with research_queue:
            response = await client.generate(
                system_prompt="You are a research assistant.",
                user_message="Explain quantum computing in simple terms."
            )
            print(response)
    
    # Run test
    asyncio.run(test_improved_client())