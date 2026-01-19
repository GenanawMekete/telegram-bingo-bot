#!/usr/bin/env python3
"""
Production entry point for Render.
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Eventlet monkey patch
import eventlet
eventlet.monkey_patch()

# Import the Flask app
from backend.app import app, socketio, init_database

def start_server():
    """Start the production server."""
    print("🚀 Starting Bingo backend...")
    print(f"🐍 Python: {sys.version}")
    print(f"📁 Directory: {os.getcwd()}")
    
    # Initialize database
    print("🗄️ Initializing database...")
    init_database()
    
    if os.environ.get('RENDER'):
        port = int(os.environ.get('PORT', 10000))
        print(f"🌐 Production mode on port {port}")
        
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,
            log_output=True
        )
    else:
        print("🔧 Development mode on port 5000")
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=True
        )

if __name__ == '__main__':
    start_server()
