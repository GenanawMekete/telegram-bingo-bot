#!/usr/bin/env python3
"""
Database setup script for Render.
Run this manually after database is created.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app, db
from backend.card_generator import generate_all_cards

print("Setting up database for production...")

with app.app_context():
    # Create all tables
    print("Creating database tables...")
    db.create_all()
    
    # Generate cards
    print("Generating 400 bingo cards...")
    try:
        generate_all_cards()
        print("✅ Database setup complete!")
    except Exception as e:
        print(f"⚠️  Note: {e}")
        print("Cards may already exist.")
