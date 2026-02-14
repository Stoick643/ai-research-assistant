import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from src.utils.config import Config, LLMConfig, AgentConfig
from src.utils.llm import create_llm_client, OpenAIClient, AnthropicClient


class TestConfig:
    def test_llm_config_creation(self):
        config = LLMConfig(
            provider="openai",
            api_key="test-key",
            model="gpt-4"
        )
        assert config.provider == "openai"
        assert config.api_key == "test-key"
        assert config.model == "gpt-4"
    
    def test_agent_config_defaults(self):
        config = AgentConfig()
        assert config.max_iterations == 10
        assert config.timeout == 300
        assert config.memory_size == 1000
    
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-openai-key",
        "OPENAI_MODEL": "gpt-3.5-turbo"
    })
    def test_config_from_env_openai(self):
        config = Config.from_env()
        assert config.llm.provider == "openai"
        assert config.llm.api_key == "test-openai-key"
        assert config.llm.model == "gpt-3.5-turbo"
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "ANTHROPIC_MODEL": "claude-3-haiku-20240307"
    }, clear=True)
    def test_config_from_env_anthropic(self):
        config = Config.from_env()
        assert config.llm.provider == "anthropic"
        assert config.llm.api_key == "test-anthropic-key"
        assert config.llm.model == "claude-3-haiku-20240307"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_config_from_env_no_keys(self):
        with pytest.raises(ValueError, match="Either OPENAI_API_KEY or ANTHROPIC_API_KEY must be set"):
            Config.from_env()
    
    def test_config_to_dict(self):
        llm_config = LLMConfig(provider="openai", api_key="test", model="gpt-4")
        config = Config(llm=llm_config)
        data = config.to_dict()
        assert isinstance(data, dict)
        assert data["llm"]["provider"] == "openai"
    
    def test_config_from_dict(self):
        data = {
            "llm": {
                "provider": "openai",
                "api_key": "test",
                "model": "gpt-4"
            }
        }
        config = Config.from_dict(data)
        assert config.llm.provider == "openai"
        assert config.llm.api_key == "test"


class TestLLMClient:
    def test_create_openai_client(self):
        client = create_llm_client("openai", api_key="test-key")
        assert isinstance(client, OpenAIClient)
    
    def test_create_anthropic_client(self):
        client = create_llm_client("anthropic", api_key="test-key")
        assert isinstance(client, AnthropicClient)
    
    def test_create_unsupported_client(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_client("unsupported", api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_openai_client_generate(self):
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Test response"
            mock_openai.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            client = OpenAIClient(api_key="test-key")
            response = await client.generate("System prompt", "User message")
            
            assert response == "Test response"
            mock_openai.return_value.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_anthropic_client_generate(self):
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content[0].text = "Test response"
            mock_anthropic.return_value.messages.create = AsyncMock(return_value=mock_response)
            
            client = AnthropicClient(api_key="test-key")
            response = await client.generate("System prompt", "User message")
            
            assert response == "Test response"
            mock_anthropic.return_value.messages.create.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])