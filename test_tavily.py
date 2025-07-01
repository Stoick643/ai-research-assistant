#!/usr/bin/env python3
"""
Simple Tavily API test to debug the web search issue.
"""

import os
from tavily import TavilyClient

def test_tavily():
    print("🔍 Testing Tavily API...")
    
    # Check API key
    api_key = os.getenv("TAVILY_API_KEY")
    print(f"API Key present: {bool(api_key)}")
    if api_key:
        print(f"API Key length: {len(api_key)}")
        print(f"API Key starts with: {api_key[:8]}...")
    
    if not api_key:
        print("❌ TAVILY_API_KEY not found in environment")
        return
    
    try:
        # Initialize client
        print("\n📡 Initializing Tavily client...")
        client = TavilyClient(api_key=api_key)
        print("✅ Client initialized successfully")
        
        # Test simple search
        print("\n🔎 Testing search...")
        query = "artificial intelligence"
        print(f"Query: {query}")
        
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=3
        )
        
        print(f"✅ Search completed!")
        print(f"Response type: {type(response)}")
        print(f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        # Check results structure
        if isinstance(response, dict):
            results = response.get("results")
            print(f"Results type: {type(results)}")
            print(f"Results value: {results}")
            
            if results is None:
                print("⚠️  Results is None - this is the issue!")
            elif isinstance(results, list):
                print(f"✅ Results is a list with {len(results)} items")
                if results:
                    print(f"First result keys: {list(results[0].keys())}")
            else:
                print(f"❌ Results is not a list: {type(results)}")
        
        print(f"\n📄 Full response:")
        print(response)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_tavily()