#!/usr/bin/env python3
"""
Test DeepSeek client directly to verify it works.
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import the improved client
from improved_rate_limiting import ImprovedDeepSeekClient

async def test_deepseek_client():
    """Test DeepSeek client directly."""
    
    print("🧪 Testing DeepSeek Client Directly")
    print("=" * 50)
    
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY')
    print(f"DeepSeek API Key: {deepseek_key[:20]}..." if deepseek_key else "❌ No DeepSeek API key")
    
    if not deepseek_key:
        print("❌ No DeepSeek API key found")
        return False
    
    client = ImprovedDeepSeekClient(api_key=deepseek_key)
    
    try:
        response = await client.generate(
            system_prompt="You are a helpful assistant.",
            user_message="What is 2+2? Answer in one word.",
            max_tokens=50
        )
        
        print(f"✅ DeepSeek response: {response}")
        return True
        
    except Exception as e:
        print(f"❌ DeepSeek error: {e}")
        print(f"❌ Error type: {type(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_deepseek_client())
    if success:
        print("\n🎉 DeepSeek client works!")
    else:
        print("\n💥 DeepSeek client failed!")