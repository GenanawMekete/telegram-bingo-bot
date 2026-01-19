#!/usr/bin/env python3
"""
Production entry point for Render.
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the app
from backend.app import app, socketio, init_database

def main():
    """Start the server."""
    print("🚀 Starting Bingo backend...")
    print(f"🐍 Python: {sys.version}")
    
    # Initialize database
    init_database()
    
    if os.environ.get('RENDER'):
        port = int(os.environ.get('PORT', 10000))
        print(f"🌐 Production mode on port {port}")
        
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,
            allow_unsafe_werkzeug=True,
            use_reloader=False
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
    main()
