#!/usr/bin/env python3
"""
Simple Tavily search test - no complexity, just search and print results.
"""

from tavily import TavilyClient

def simple_search():
    print("🔍 Simple Tavily Search Test")
    
    # Hardcoded API key for testing
    api_key = "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"
    
    try:
        # Initialize client
        client = TavilyClient(api_key=api_key)
        print("✅ Client initialized")
        
        # Simple search
        query = "artificial intelligence trends 2025"
        print(f"🔎 Searching: {query}")
        
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=3
        )
        
        print(f"✅ Search successful!")
        print(f"📊 Response type: {type(response)}")
        
        if isinstance(response, dict):
            print(f"📋 Keys: {list(response.keys())}")
            
            results = response.get("results", [])
            print(f"📄 Found {len(results)} results")
            
            for i, result in enumerate(results, 1):
                print(f"\n--- Result {i} ---")
                print(f"Title: {result.get('title', 'N/A')}")
                print(f"URL: {result.get('url', 'N/A')}")
                print(f"Content: {result.get('content', 'N/A')[:200]}...")
                print(f"Score: {result.get('score', 'N/A')}")
        else:
            print(f"❌ Unexpected response type: {type(response)}")
            print(f"Response: {response}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_search()