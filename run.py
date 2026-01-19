#!/usr/bin/env python3
"""
Production entry point for Render deployment.
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Gevent monkey patch - MUST BE FIRST
from gevent import monkey
monkey.patch_all()

# Import the Flask app
from backend.app import app, socketio, init_database

def start_server():
    """Start the production server."""
    print("Starting server...")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Environment: {'production' if os.environ.get('RENDER') else 'development'}")
    
    # Initialize database
    print("Initializing database...")
    init_database()
    
    if os.environ.get('RENDER'):
        # Production mode
        port = int(os.environ.get('PORT', 10000))
        print(f"Starting production server on port {port}")
        
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,
            allow_unsafe_werkzeug=True,
            use_reloader=False,
            log_output=True
        )
    else:
        # Development mode
        print("Starting development server on port 5000")
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=True,
            allow_unsafe_werkzeug=True
        )

if __name__ == '__main__':
    start_server()
