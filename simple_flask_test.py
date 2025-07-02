#!/usr/bin/env python3
"""
Simple Flask test without complex integrations.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

def create_simple_app():
    """Create a simple Flask app for testing."""
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-key'
    CORS(app)
    
    @app.route('/')
    def home():
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>AI Research Assistant - Test</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">🔍 AI Research Assistant</a>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row">
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h4 class="mb-0">🚀 Flask App Test - Working!</h4>
                    </div>
                    <div class="card-body">
                        <p class="lead">Your Flask web backend is successfully running!</p>
                        <h5>✅ What's Working:</h5>
                        <ul>
                            <li>Flask application factory</li>
                            <li>Bootstrap UI framework</li>
                            <li>Basic routing</li>
                            <li>Template rendering</li>
                            <li>Static file serving</li>
                        </ul>
                        
                        <h5>📋 Next Steps:</h5>
                        <ol>
                            <li>Set up your API keys (OPENAI_API_KEY, TAVILY_API_KEY)</li>
                            <li>Start Redis server for Celery (if using background tasks)</li>
                            <li>Test the research functionality</li>
                        </ol>
                        
                        <div class="mt-3">
                            <button class="btn btn-primary" onclick="testAPI()">Test API</button>
                        </div>
                        <div id="api-result" class="mt-3"></div>
                    </div>
                </div>
            </div>
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header">
                        <h6>📊 Quick Stats</h6>
                    </div>
                    <div class="card-body text-center">
                        <div class="h4 text-success">✓</div>
                        <small>Flask App Running</small>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function testAPI() {
        fetch('/api/test')
            .then(response => response.json())
            .then(data => {
                document.getElementById('api-result').innerHTML = 
                    '<div class="alert alert-success">API Test: ' + data.message + '</div>';
            })
            .catch(error => {
                document.getElementById('api-result').innerHTML = 
                    '<div class="alert alert-danger">API Test Failed: ' + error + '</div>';
            });
    }
    </script>
</body>
</html>
        """)
    
    @app.route('/api/test')
    def api_test():
        try:
            return jsonify({
                'status': 'success',
                'message': 'API endpoint working correctly!',
                'flask_version': '3.1.1'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'API error: {str(e)}'
            }), 500
    
    return app

if __name__ == '__main__':
    print("🚀 Starting Simple Flask Test Server...")
    print("🌐 Open your browser to: http://localhost:5001")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    app = create_simple_app()
    app.run(host='0.0.0.0', port=5001, debug=True)