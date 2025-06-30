import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from src.agents import BaseAgent, ReasoningAgent, ReactiveAgent
from src.agents.base import Message, AgentState
from src.utils.llm import LLMClient


class MockLLMClient(LLMClient):
    def __init__(self, responses=None):
        self.responses = responses or ["Mock response"]
        self.call_count = 0
    
    async def generate(self, system_prompt, user_message, **kwargs):
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return response


class TestAgent(BaseAgent):
    async def process_message(self, message):
        if isinstance(message, str):
            message = Message(role="user", content=message)
        response = Message(role="assistant", content=f"Processed: {message.content}")
        self.add_message(message)
        self.add_message(response)
        return response
    
    async def plan(self, goal):
        return [f"Task 1 for {goal}", f"Task 2 for {goal}"]
    
    async def execute_task(self, task):
        return {"task": task, "status": "completed", "result": f"Executed {task}"}


class TestBaseAgent:
    def test_init(self):
        agent = TestAgent("TestAgent", "A test agent")
        assert agent.name == "TestAgent"
        assert agent.description == "A test agent"
        assert agent.max_iterations == 10
        assert isinstance(agent.state, AgentState)
    
    def test_add_message(self):
        agent = TestAgent("TestAgent")
        agent.add_message("Hello")
        assert len(agent.state.messages) == 1
        assert agent.state.messages[0].content == "Hello"
        assert agent.state.messages[0].role == "user"
    
    def test_context_management(self):
        agent = TestAgent("TestAgent")
        agent.set_context("key1", "value1")
        assert agent.get_context("key1") == "value1"
        assert agent.get_context("key2", "default") == "default"
    
    @pytest.mark.asyncio
    async def test_run(self):
        agent = TestAgent("TestAgent")
        result = await agent.run("Test goal")
        
        assert result["goal"] == "Test goal"
        assert result["tasks_completed"] == 2
        assert len(result["results"]) == 2
        assert "Test goal" in agent.state.goals


class TestReasoningAgent:
    @pytest.mark.asyncio
    async def test_process_message(self):
        mock_client = MockLLMClient(["Reasoned response"])
        agent = ReasoningAgent("ReasoningAgent", mock_client)
        
        response = await agent.process_message("Test question")
        assert response.content == "Reasoned response"
        assert len(agent.state.messages) == 2
    
    @pytest.mark.asyncio
    async def test_plan(self):
        mock_client = MockLLMClient(["1. First task\n2. Second task\n3. Third task"])
        agent = ReasoningAgent("ReasoningAgent", mock_client)
        
        tasks = await agent.plan("Test goal")
        assert len(tasks) == 3
        assert tasks[0] == "First task"
        assert tasks[1] == "Second task"
        assert tasks[2] == "Third task"


class TestReactiveAgent:
    @pytest.mark.asyncio
    async def test_tool_registration(self):
        mock_client = MockLLMClient()
        agent = ReactiveAgent("ReactiveAgent", mock_client)
        
        def test_tool(args):
            return f"Tool result: {args}"
        
        agent.register_tool("test_tool", test_tool)
        assert "test_tool" in agent.tools
    
    @pytest.mark.asyncio
    async def test_event_handling(self):
        mock_client = MockLLMClient()
        agent = ReactiveAgent("ReactiveAgent", mock_client)
        
        events_received = []
        
        async def event_handler(data):
            events_received.append(data)
        
        agent.register_event_handler("test_event", event_handler)
        await agent.emit_event("test_event", {"test": "data"})
        
        assert len(events_received) == 1
        assert events_received[0]["test"] == "data"
    
    @pytest.mark.asyncio
    async def test_tool_usage(self):
        mock_client = MockLLMClient(["USE_TOOL: test_tool hello world"])
        agent = ReactiveAgent("ReactiveAgent", mock_client)
        
        async def test_tool(args):
            return f"Tool executed with: {args}"
        
        agent.register_tool("test_tool", test_tool)
        
        response = await agent.process_message("Use the test tool")
        assert "Tool executed with: hello world" in response.content


if __name__ == "__main__":
    pytest.main([__file__])