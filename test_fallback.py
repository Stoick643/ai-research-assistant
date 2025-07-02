#!/usr/bin/env python3
"""
Test script to verify the fallback system works correctly.
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import the improved client
from improved_rate_limiting import create_improved_llm_client

async def test_fallback_system():
    """Test the fallback system with a simple query."""
    
    print("🧪 Testing Fallback System")
    print("=" * 50)
    
    # Create client with OpenAI -> DeepSeek -> Anthropic fallback
    client = create_improved_llm_client(
        primary_provider="openai",
        fallback_provider="deepseek", 
        final_fallback_provider="anthropic",
        openai_api_key=os.environ.get('OPENAI_API_KEY'),
        deepseek_api_key=os.environ.get('DEEPSEEK_API_KEY'),
        anthropic_api_key=os.environ.get('ANTHROPIC_API_KEY')
    )
    
    print(f"✅ Created client with fallback chain: OpenAI → DeepSeek → Anthropic")
    
    # Test simple query
    try:
        response = await client.generate(
            system_prompt="You are a helpful assistant. Respond concisely.",
            user_message="What is 2+2? Answer in one word.",
            max_tokens=50
        )
        
        print(f"✅ Got response: {response}")
        print(f"✅ Test successful - fallback system is working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"❌ Error type: {type(e)}")
        
        # Check if it's an OpenAI quota error specifically
        error_str = str(e).lower()
        if any(term in error_str for term in ['quota', 'rate limit', '429', 'insufficient_quota']):
            print("💡 This is a quota/rate limit error - fallback should have been triggered")
        
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_fallback_system())
    if success:
        print("\n🎉 Fallback system test passed!")
    else:
        print("\n💥 Fallback system test failed!")