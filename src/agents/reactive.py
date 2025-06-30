from typing import Any, Dict, List, Union, Callable, Optional
import asyncio
from .base import BaseAgent, Message
from ..utils.llm import LLMClient


class ReactiveAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools: Optional[Dict[str, Callable]] = None,
        description: str = "An agent that reacts to events and uses tools",
        **kwargs
    ):
        super().__init__(name, description, **kwargs)
        self.llm_client = llm_client
        self.tools = tools or {}
        self.event_handlers = {}
        
    def register_tool(self, name: str, tool: Callable) -> None:
        self.tools[name] = tool
        self.logger.info("Tool registered", tool_name=name)
        
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        self.logger.info("Event handler registered", event_type=event_type)
        
    async def emit_event(self, event_type: str, data: Any) -> None:
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    self.logger.error("Event handler failed", 
                                    event_type=event_type, error=str(e))
    
    async def process_message(self, message: Union[str, Message]) -> Message:
        if isinstance(message, str):
            message = Message(role="user", content=message)
            
        self.add_message(message)
        await self.emit_event("message_received", message)
        
        tool_descriptions = ""
        if self.tools:
            tool_descriptions = f"Available tools: {list(self.tools.keys())}"
        
        system_prompt = f"""
        You are {self.name}, {self.description}.
        
        {tool_descriptions}
        
        Current context: {self.state.context}
        
        Analyze the message and decide if you need to use any tools.
        If you need to use a tool, respond with: USE_TOOL: <tool_name> <arguments>
        Otherwise, provide a direct response.
        """
        
        response = await self.llm_client.generate(
            system_prompt=system_prompt,
            user_message=message.content
        )
        
        if response.startswith("USE_TOOL:"):
            parts = response[9:].strip().split(' ', 1)
            tool_name = parts[0]
            tool_args = parts[1] if len(parts) > 1 else ""
            
            if tool_name in self.tools:
                try:
                    tool_result = await self.tools[tool_name](tool_args)
                    response = f"Used tool {tool_name}: {tool_result}"
                    await self.emit_event("tool_used", {
                        "tool": tool_name,
                        "args": tool_args,
                        "result": tool_result
                    })
                except Exception as e:
                    response = f"Tool {tool_name} failed: {str(e)}"
                    self.logger.error("Tool execution failed", 
                                    tool=tool_name, error=str(e))
            else:
                response = f"Tool {tool_name} not found"
        
        response_message = Message(
            role="assistant",
            content=response,
            metadata={"agent_type": "reactive"}
        )
        
        self.add_message(response_message)
        await self.emit_event("message_sent", response_message)
        return response_message
    
    async def plan(self, goal: str) -> List[str]:
        tool_info = ""
        if self.tools:
            tool_info = f"You have access to these tools: {list(self.tools.keys())}"
        
        planning_prompt = f"""
        Goal: {goal}
        {tool_info}
        
        Create a reactive plan that responds to events and uses available tools.
        Break down into tasks that can trigger reactions or use tools.
        Return tasks as a numbered list.
        """
        
        response = await self.llm_client.generate(
            system_prompt="You are a reactive planning assistant.",
            user_message=planning_prompt
        )
        
        tasks = []
        for line in response.split('\n'):
            line = line.strip()
            if line and any(line.startswith(f"{i}.") for i in range(1, 20)):
                task = line.split('.', 1)[1].strip()
                if task:
                    tasks.append(task)
        
        return tasks
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        execution_prompt = f"""
        Task: {task}
        Available tools: {list(self.tools.keys())}
        Current context: {self.state.context}
        
        Execute this task. If you need tools, specify which ones and how to use them.
        """
        
        response = await self.llm_client.generate(
            system_prompt=f"You are {self.name}. Execute tasks using available tools.",
            user_message=execution_prompt
        )
        
        result = {
            "task": task,
            "execution_plan": response,
            "status": "completed",
            "tools_available": list(self.tools.keys()),
            "metadata": {
                "execution_method": "reactive",
                "timestamp": asyncio.get_event_loop().time()
            }
        }
        
        await self.emit_event("task_completed", result)
        return result