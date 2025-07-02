#!/usr/bin/env python3
"""
Check the status of a specific research request.
"""
import requests
import json

def check_research_status(research_id=1):
    """Check the detailed status of a research request."""
    
    base_url = "http://127.0.0.1:5007"
    
    print(f"🔍 Checking Research ID: {research_id}")
    print("=" * 50)
    
    try:
        # Check the progress page
        response = requests.get(f"{base_url}/research/{research_id}")
        if response.status_code == 200:
            html = response.text
            
            # Extract key information from HTML
            if 'progress:' in html.lower():
                # Try to find progress percentage
                import re
                progress_match = re.search(r'(\d+)%', html)
                if progress_match:
                    progress = progress_match.group(1)
                    print(f"📊 Progress: {progress}%")
            
            # Check status
            if 'completed' in html.lower():
                print("✅ Status: COMPLETED")
            elif 'failed' in html.lower():
                print("❌ Status: FAILED")
            elif 'progress' in html.lower():
                print("🔄 Status: IN PROGRESS")
            else:
                print("❓ Status: UNKNOWN")
            
            # Look for error messages
            if 'error' in html.lower():
                # Try to extract error text
                error_start = html.lower().find('error')
                if error_start != -1:
                    error_section = html[error_start:error_start+300]
                    print(f"⚠️  Error found: {error_section[:200]}...")
            
            # Check for the graceful degradation message
            if 'temporarily unavailable' in html.lower():
                print("✅ Graceful degradation message detected!")
            elif 'high demand' in html.lower():
                print("✅ Graceful degradation message detected!")
            
            print(f"\n📝 Full HTML length: {len(html)} characters")
            
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
    
    except Exception as e:
        print(f"❌ Error checking status: {e}")

    # Also check the API endpoint
    try:
        api_response = requests.get(f"{base_url}/api/research/{research_id}/status")
        if api_response.status_code == 200:
            data = api_response.json()
            print(f"\n🔌 API Status: {json.dumps(data, indent=2)}")
        else:
            print(f"\n❌ API Error: {api_response.status_code}")
    except Exception as e:
        print(f"\n❌ API check failed: {e}")

if __name__ == "__main__":
    # Check the most recent research request
    check_research_status(1)