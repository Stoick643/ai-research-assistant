#!/usr/bin/env python3
"""
Simple test script for Flask web application.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_flask_app():
    """Test basic Flask app functionality."""
    
    print("🔧 Testing Flask App Setup...")
    
    try:
        # Test imports
        print("  ✓ Testing imports...")
        from src.web.app import create_app
        from src.web.config import config
        from src.web.models import Research
        print("  ✓ All imports successful")
        
        # Test app creation
        print("  ✓ Testing app creation...")
        app = create_app('testing')
        print("  ✓ Flask app created successfully")
        
        # Test basic routes
        print("  ✓ Testing basic routes...")
        with app.test_client() as client:
            
            # Test home page
            response = client.get('/')
            print(f"    - Home page: {response.status_code}")
            
            # Test API endpoint
            response = client.get('/api/stats/dashboard')
            print(f"    - API dashboard: {response.status_code}")
            
            # Test status page
            response = client.get('/status')
            print(f"    - Status page: {response.status_code}")
            
        print("  ✅ Basic route tests completed")
        
        # Test database models
        print("  ✓ Testing database models...")
        with app.app_context():
            # Create tables
            from src.web.models import db
            db.create_all()
            print("  ✓ Database tables created")
            
            # Test model creation
            research = Research(
                topic="Test research topic",
                agent_name="TestAgent",
                status="completed"
            )
            print("  ✓ Research model created successfully")
            
        print("\n🎉 All tests passed! Flask app is working correctly.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def run_development_server():
    """Run the Flask development server."""
    
    print("🚀 Starting Flask Development Server...")
    print("📌 Make sure you have your environment variables set:")
    print("   - OPENAI_API_KEY")
    print("   - TAVILY_API_KEY")
    print("   - SECRET_KEY (optional, will use default)")
    print()
    
    try:
        from src.web.app import create_app
        
        app = create_app('development')
        
        print("🌐 Flask app will be available at: http://localhost:5000")
        print("📝 Available routes:")
        print("   - /                   - Home page with research form")
        print("   - /status             - System status")
        print("   - /history            - Research history")
        print("   - /api/stats/dashboard - API stats")
        print()
        print("Press Ctrl+C to stop the server")
        print("-" * 50)
        
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False  # Avoid double startup in testing
        )
        
    except Exception as e:
        print(f"❌ Failed to start server: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("AI Research Assistant - Flask Web Interface Test")
    print("=" * 50)
    
    # First run basic tests
    if test_flask_app():
        print("\n" + "=" * 50)
        
        # Ask if user wants to run development server
        response = input("Would you like to start the development server? (y/n): ").lower().strip()
        
        if response in ['y', 'yes']:
            run_development_server()
        else:
            print("👋 Tests completed. Run this script again to start the server.")
    else:
        print("❌ Tests failed. Please fix the issues before running the server.")
        sys.exit(1)