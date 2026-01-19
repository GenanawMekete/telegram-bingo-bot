#!/usr/bin/env python3
"""
Production entry point for Render deployment.
This file allows gunicorn to find the Flask app.
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from backend
from backend.app import app, socketio

# Initialize database for production
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

# Initialize database when starting in production
if os.environ.get('RENDER'):
    print("Starting production database initialization...")
    init_production_database()

# Create app instance for gunicorn
if __name__ == "__main__":
    # Development mode
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
