import asyncio
import os
from dotenv import load_dotenv
from src.agents import ReasoningAgent
from src.utils import LLMClient, create_llm_client, setup_logging

load_dotenv()
setup_logging()


async def main():
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    provider = "openai" if os.getenv("OPENAI_API_KEY") else "anthropic"
    if not api_key:
        print("Please set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable")
        return
    
    llm_client = create_llm_client(provider, api_key=api_key)
    
    agent = ReasoningAgent(
        name="ChatBot",
        llm_client=llm_client,
        description="A helpful reasoning agent that can answer questions and solve problems"
    )
    
    print("Chat Agent initialized! Type 'quit' to exit.")
    print("-" * 50)
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("Goodbye!")
            break
            
        if not user_input:
            continue
            
        try:
            response = await agent.process_message(user_input)
            print(f"Agent: {response.content}")
            print("-" * 50)
            
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())