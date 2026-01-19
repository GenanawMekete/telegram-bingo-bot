#!/usr/bin/env python3
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.utils import init_db
from backend.app import app, db
from backend.card_generator import generate_all_cards

def initialize_database():
    """Initialize the database and generate cards."""
    print("Initializing database...")
    
    # Initialize bot database
    init_db()
    
    # Initialize backend database with Flask context
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Generate 400 bingo cards
        generate_all_cards()
    
    print("✅ Database initialization complete!")

if __name__ == '__main__':
    initialize_database()
