import asyncio
import os
from dotenv import load_dotenv
from src.agents import ReactiveAgent
from src.utils import create_llm_client, setup_logging

load_dotenv()
setup_logging()


async def file_tool(args: str) -> str:
    try:
        if args.startswith("read"):
            filename = args.split(" ", 1)[1]
            with open(filename, 'r') as f:
                return f"File content: {f.read()[:500]}..."
        elif args.startswith("write"):
            parts = args.split(" ", 2)
            filename = parts[1]
            content = parts[2]
            with open(filename, 'w') as f:
                f.write(content)
            return f"Wrote to {filename}"
        elif args.startswith("list"):
            import os
            files = os.listdir(".")
            return f"Files: {', '.join(files)}"
        else:
            return "Usage: read <filename> | write <filename> <content> | list"
    except Exception as e:
        return f"File operation failed: {str(e)}"


async def calculate_tool(args: str) -> str:
    try:
        result = eval(args)
        return f"Result: {result}"
    except Exception as e:
        return f"Calculation failed: {str(e)}"


async def main():
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    provider = "openai" if os.getenv("OPENAI_API_KEY") else "anthropic"
    
    if not api_key:
        print("Please set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable")
        return
    
    llm_client = create_llm_client(provider, api_key=api_key)
    
    agent = ReactiveAgent(
        name="TaskExecutor",
        llm_client=llm_client,
        description="An agent that can execute tasks using various tools"
    )
    
    agent.register_tool("file", file_tool)
    agent.register_tool("calculate", calculate_tool)
    
    async def on_tool_used(data):
        print(f"[TOOL USED] {data['tool']} with args: {data['args']}")
    
    agent.register_event_handler("tool_used", on_tool_used)
    
    print("Task Executor Agent initialized!")
    print("Available tools: file (read/write/list), calculate")
    print("Type 'quit' to exit or 'run <goal>' to execute a goal.")
    print("-" * 50)
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("Goodbye!")
            break
            
        if not user_input:
            continue
            
        try:
            if user_input.startswith("run "):
                goal = user_input[4:]
                print(f"Executing goal: {goal}")
                result = await agent.run(goal)
                print(f"Goal completed! Tasks: {result['tasks_completed']}")
                print("-" * 50)
            else:
                response = await agent.process_message(user_input)
                print(f"Agent: {response.content}")
                print("-" * 50)
                
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())