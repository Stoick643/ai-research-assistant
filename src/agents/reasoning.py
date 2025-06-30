from typing import Any, Dict, List, Union
import asyncio
from .base import BaseAgent, Message
from ..utils.llm import LLMClient


class ReasoningAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        description: str = "An agent that uses reasoning to solve problems",
        **kwargs
    ):
        super().__init__(name, description, **kwargs)
        self.llm_client = llm_client
        
    async def process_message(self, message: Union[str, Message]) -> Message:
        if isinstance(message, str):
            message = Message(role="user", content=message)
            
        self.add_message(message)
        
        system_prompt = f"""
        You are {self.name}, {self.description}.
        
        Current context: {self.state.context}
        Previous messages: {[m.content for m in self.state.messages[-5:]]}
        
        Think step by step and provide a reasoned response.
        """
        
        response = await self.llm_client.generate(
            system_prompt=system_prompt,
            user_message=message.content
        )
        
        response_message = Message(
            role="assistant",
            content=response,
            metadata={"reasoning_type": "step_by_step"}
        )
        
        self.add_message(response_message)
        return response_message
    
    async def plan(self, goal: str) -> List[str]:
        planning_prompt = f"""
        Goal: {goal}
        
        Break this goal down into specific, actionable tasks.
        Consider dependencies and logical order.
        Return a list of tasks, one per line, starting with "1.", "2.", etc.
        """
        
        response = await self.llm_client.generate(
            system_prompt="You are a planning assistant. Break down goals into actionable tasks.",
            user_message=planning_prompt
        )
        
        tasks = []
        for line in response.split('\n'):
            line = line.strip()
            if line and any(line.startswith(f"{i}.") for i in range(1, 20)):
                task = line.split('.', 1)[1].strip()
                if task:
                    tasks.append(task)
        
        self.logger.info("Generated plan", goal=goal, tasks=tasks)
        return tasks
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        execution_prompt = f"""
        Task: {task}
        
        Current context: {self.state.context}
        Completed tasks: {self.state.completed_tasks}
        
        Execute this task step by step. Explain your reasoning and provide the result.
        If you need to gather information or perform actions, describe what you would do.
        """
        
        response = await self.llm_client.generate(
            system_prompt=f"You are {self.name}. Execute the given task with clear reasoning.",
            user_message=execution_prompt
        )
        
        result = {
            "task": task,
            "reasoning": response,
            "status": "completed",
            "metadata": {
                "execution_method": "reasoning",
                "timestamp": asyncio.get_event_loop().time()
            }
        }
        
        self.logger.info("Task executed", task=task, result=result)
        return result