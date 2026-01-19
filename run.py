#!/usr/bin/env python3
"""
Production entry point for Render.
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app, socketio, init_database

def main():
    print("🚀 Starting Bingo backend...")
    print(f"Python: {sys.version}")
    
    # Initialize database
    init_database()
    
    # Get port
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting on port {port}")
    
    # Run the app
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True,
        use_reloader=False
    )

if __name__ == '__main__':
    main()
