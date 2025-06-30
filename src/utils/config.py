import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class LLMConfig(BaseModel):
    provider: str = Field(default="openai", description="LLM provider (openai, anthropic)")
    api_key: str = Field(..., description="API key for the LLM provider")
    model: str = Field(default="gpt-4", description="Model name to use")
    base_url: Optional[str] = Field(default=None, description="Custom base URL for API")
    max_tokens: int = Field(default=1000, description="Maximum tokens for generation")
    temperature: float = Field(default=0.7, description="Temperature for generation")


class AgentConfig(BaseModel):
    max_iterations: int = Field(default=10, description="Maximum iterations for agent execution")
    timeout: int = Field(default=300, description="Timeout in seconds for agent operations")
    memory_size: int = Field(default=1000, description="Maximum memory size for agent state")


class Config(BaseModel):
    llm: LLMConfig
    agent: AgentConfig = Field(default_factory=AgentConfig)
    redis_url: Optional[str] = Field(default=None, description="Redis URL for caching")
    database_url: Optional[str] = Field(default=None, description="Database URL for persistence")
    log_level: str = Field(default="INFO", description="Logging level")
    
    @classmethod
    def from_env(cls) -> "Config":
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        if openai_key:
            provider = "openai"
            api_key = openai_key
            model = os.getenv("OPENAI_MODEL", "gpt-4")
        elif anthropic_key:
            provider = "anthropic"
            api_key = anthropic_key
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
        else:
            raise ValueError("Either OPENAI_API_KEY or ANTHROPIC_API_KEY must be set")
        
        llm_config = LLMConfig(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=os.getenv("LLM_BASE_URL"),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1000")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
        )
        
        agent_config = AgentConfig(
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "10")),
            timeout=int(os.getenv("AGENT_TIMEOUT", "300")),
            memory_size=int(os.getenv("AGENT_MEMORY_SIZE", "1000"))
        )
        
        return cls(
            llm=llm_config,
            agent=agent_config,
            redis_url=os.getenv("REDIS_URL"),
            database_url=os.getenv("DATABASE_URL"),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        return cls(**data)