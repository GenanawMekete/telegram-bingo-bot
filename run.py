#!/usr/bin/env python3
"""
Production entry point for Render deployment with gevent.
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Gevent monkey patch (important!)
from gevent import monkey
monkey.patch_all()

# Import from backend
from backend.app import app, socketio

def init_production_database():
    """Initialize database for production."""
    from backend.app import db
    from backend.card_generator import generate_all_cards
    from backend.models import BingoCard
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Generate cards if none exist
        if BingoCard.query.count() == 0:
            print("Generating 400 bingo cards for production...")
            generate_all_cards()
            print(f"Generated {BingoCard.query.count()} cards.")
        else:
            print(f"Database already has {BingoCard.query.count()} cards.")

if __name__ == "__main__":
    # Check if running on Render
    if os.environ.get('RENDER'):
        print("Starting production server with gevent...")
        init_production_database()
        
        # Get port from environment
        port = int(os.environ.get('PORT', 10000))
        
        # Run with gevent production server
        from gevent.pywsgi import WSGIServer
        from geventwebsocket.handler import WebSocketHandler
        
        http_server = WSGIServer(('0.0.0.0', port), app, handler_class=WebSocketHandler)
        print(f"Server running on port {port}")
        http_server.serve_forever()
    else:
        # Development mode
        print("Starting development server...")
        init_production_database()
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
