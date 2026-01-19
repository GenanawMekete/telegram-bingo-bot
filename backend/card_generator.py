"""
Generate 400 bingo cards.
"""
import json
import random
from backend.app import db
from backend.models import BingoCard

def generate_bingo_card():
    """Generate a single 5x5 Bingo card."""
    columns = {
        'B': sorted(random.sample(range(1, 16), 5)),
        'I': sorted(random.sample(range(16, 31), 5)),
        'N': sorted(random.sample(range(31, 46), 5)),
        'G': sorted(random.sample(range(46, 61), 5)),
        'O': sorted(random.sample(range(61, 76), 5))
    }
    
    card = []
    for i in range(5):
        row = [
            columns['B'][i],
            columns['I'][i],
            columns['N'][i],
            columns['G'][i],
            columns['O'][i]
        ]
        card.append(row)
    
    # Middle cell is FREE
    card[2][2] = 'FREE'
    
    return card

def generate_all_cards():
    """Generate all 400 unique bingo cards."""
    print("🃏 Generating bingo cards...")
    
    # Delete existing cards
    BingoCard.query.delete()
    
    cards_generated = 0
    existing_cards = set()
    
    for card_number in range(1, 401):
        for _ in range(100):  # Try 100 times max
            card = generate_bingo_card()
            card_json = json.dumps(card)
            
            if card_json not in existing_cards:
                bingo_card = BingoCard(
                    card_number=card_number,
                    card_data=card_json,
                    is_used=False
                )
                db.session.add(bingo_card)
                existing_cards.add(card_json)
                cards_generated += 1
                break
    
    db.session.commit()
    print(f"✅ Generated {cards_generated} cards")

if __name__ == '__main__':
    from backend.app import app
    with app.app_context():
        generate_all_cards()
