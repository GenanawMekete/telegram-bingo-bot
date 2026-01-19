#!/usr/bin/env python3
"""
Database setup script for Render.
Run this manually after deployment.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Setting up database for production...")
print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")

# Initialize gevent
from gevent import monkey
monkey.patch_all()

from backend.app import app, db
from backend.card_generator import generate_all_cards
from backend.models import BingoCard

with app.app_context():
    try:
        # Create all tables
        print("Creating database tables...")
        db.create_all()
        print("✅ Tables created successfully!")
        
        # Generate cards
        print("Checking for existing cards...")
        card_count = BingoCard.query.count()
        
        if card_count == 0:
            print("Generating 400 bingo cards...")
            generate_all_cards()
            card_count = BingoCard.query.count()
            print(f"✅ Generated {card_count} cards!")
        else:
            print(f"✅ Database already has {card_count} cards.")
        
        # Verify
        print("\n✅ Database setup complete!")
        print(f"Total cards: {BingoCard.query.count()}")
        
    except Exception as e:
        print(f"❌ Error during database setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
