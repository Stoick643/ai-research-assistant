from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
import asyncio
import structlog

logger = structlog.get_logger()


class Message(BaseModel):
    role: str = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    messages: List[Message] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    goals: List[str] = Field(default_factory=list)
    completed_tasks: List[str] = Field(default_factory=list)


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        description: str = "",
        max_iterations: int = 10,
        **kwargs
    ):
        self.name = name
        self.description = description
        self.max_iterations = max_iterations
        self.state = AgentState()
        self.logger = logger.bind(agent=name)
        
    @abstractmethod
    async def process_message(self, message: Union[str, Message]) -> Message:
        pass
    
    @abstractmethod
    async def plan(self, goal: str) -> List[str]:
        pass
    
    @abstractmethod
    async def execute_task(self, task: str) -> Dict[str, Any]:
        pass
    
    async def run(self, goal: str) -> Dict[str, Any]:
        self.logger.info("Starting agent execution", goal=goal)
        
        tasks = await self.plan(goal)
        self.state.goals.append(goal)
        
        results = []
        for i, task in enumerate(tasks):
            if i >= self.max_iterations:
                self.logger.warning("Max iterations reached", iterations=i)
                break
                
            self.logger.info("Executing task", task=task, iteration=i)
            result = await self.execute_task(task)
            results.append(result)
            self.state.completed_tasks.append(task)
            
        return {
            "goal": goal,
            "tasks_completed": len(results),
            "results": results,
            "final_state": self.state.model_dump()
        }
    
    def add_message(self, message: Union[str, Message]) -> None:
        if isinstance(message, str):
            message = Message(role="user", content=message)
        self.state.messages.append(message)
        
    def get_context(self, key: str, default: Any = None) -> Any:
        return self.state.context.get(key, default)
        
    def set_context(self, key: str, value: Any) -> None:
        self.state.context[key] = value