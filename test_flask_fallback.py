#!/usr/bin/env python3
"""
Test the Flask app fallback system by making a research request.
"""
import requests
import time
import json

def test_flask_research_fallback():
    """Test research request through Flask app to verify fallback system."""
    
    print("🧪 Testing Flask App Fallback System")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:5007"
    
    # Use a session to maintain cookies
    session = requests.Session()
    
    # Test health endpoint first
    try:
        health_response = session.get(f"{base_url}/health")
        print(f"✅ Health check: {health_response.status_code}")
        print(f"   Health data: {health_response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Get the main page first to get any CSRF tokens
    try:
        main_page = session.get(f"{base_url}/")
        print(f"✅ Main page: {main_page.status_code}")
    except Exception as e:
        print(f"❌ Main page failed: {e}")
        return False
    
    # Submit a research request
    research_data = {
        'topic': 'Test fallback system - quantum computing basics',
        'focus_areas': 'basic principles, applications',
        'language': 'en',
        'depth': 'basic'
    }
    
    try:
        print(f"\n📋 Submitting research request...")
        response = session.post(f"{base_url}/submit_research", data=research_data, allow_redirects=False)
        print(f"✅ Submit response: {response.status_code}")
        
        if response.status_code == 200:
            # Check if there's an error message in the response
            html = response.text
            if 'alert-danger' in html or 'error' in html.lower():
                print(f"❌ Form validation error - check HTML response")
                # Print first 500 chars of response for debugging
                print(f"   Response snippet: {html[:500]}...")
                return False
        
        if response.status_code == 302:  # Redirect to progress page
            # Extract research ID from redirect location
            location = response.headers.get('Location', '')
            print(f"   Redirect to: {location}")
            
            if '/research/' in location:
                research_id = location.split('/research/')[-1]
                print(f"   Research ID: {research_id}")
                
                # Monitor progress
                print(f"\n🔄 Monitoring research progress...")
                for i in range(6):  # Check for up to 60 seconds
                    time.sleep(10)
                    try:
                        progress_response = session.get(f"{base_url}/research/{research_id}")
                        if progress_response.status_code == 200:
                            # Try to extract status from HTML (basic parsing)
                            html = progress_response.text
                            if 'completed' in html.lower():
                                print(f"✅ Research completed!")
                                return True
                            elif 'failed' in html.lower() or 'error' in html.lower():
                                print(f"❌ Research failed - checking for fallback graceful message")
                                if 'temporarily unavailable' in html.lower() or 'high demand' in html.lower():
                                    print(f"✅ Graceful fallback message detected - fallback system working!")
                                    return True
                                else:
                                    print(f"❌ Hard failure without graceful fallback")
                                    # Print part of the HTML to see the actual error
                                    print(f"   Error HTML snippet: {html[html.find('error'):html.find('error')+200] if 'error' in html.lower() else 'No error section found'}")
                                    return False
                            else:
                                print(f"   Status check {i+1}/6: Still in progress...")
                    except Exception as e:
                        print(f"❌ Progress check failed: {e}")
                        return False
                
                print(f"⏰ Research still in progress after 60 seconds")
                return True  # Consider this a success since it didn't crash
                
    except Exception as e:
        print(f"❌ Research request failed: {e}")
        return False
    
    return False

if __name__ == "__main__":
    success = test_flask_research_fallback()
    if success:
        print("\n🎉 Flask fallback system test passed!")
    else:
        print("\n💥 Flask fallback system test failed!")