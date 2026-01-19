#!/usr/bin/env python3
"""
Database setup for Render.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🛠️ Setting up database...")

from backend.app import app, db
from backend.card_generator import generate_all_cards

with app.app_context():
    try:
        print("🗄️ Creating tables...")
        db.create_all()
        print("✅ Tables created")
        
        print("🃏 Generating cards...")
        generate_all_cards()
        print("✅ Cards generated")
        
        print("🎉 Database setup complete!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
