import json
import random
from backend.app import db
from backend.models import BingoCard

def generate_bingo_card(card_number):
    """Generate a single 5x5 Bingo card."""
    # Standard Bingo: B(1-15), I(16-30), N(31-45), G(46-60), O(61-75)
    columns = {
        'B': sorted(random.sample(range(1, 16), 5)),
        'I': sorted(random.sample(range(16, 31), 5)),
        'N': sorted(random.sample(range(31, 46), 5)),
        'G': sorted(random.sample(range(46, 61), 5)),
        'O': sorted(random.sample(range(61, 76), 5))
    }
    
    # Create 5x5 grid
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
    
    # Make middle cell FREE
    card[2][2] = 'FREE'
    
    return card

def generate_all_cards():
    """Generate all 400 unique bingo cards."""
    print("Generating 400 bingo cards...")
    
    existing_cards = set()
    cards_generated = 0
    
    # Check existing cards
    existing = BingoCard.query.all()
    if existing:
        print(f"Found {len(existing)} existing cards")
        return
    
    for card_number in range(1, 401):
        attempts = 0
        while attempts < 100:  # Prevent infinite loop
            card = generate_bingo_card(card_number)
            card_json = json.dumps(card)
            
            # Check if card is unique
            if card_json not in existing_cards:
                # Create bingo card record
                bingo_card = BingoCard(
                    card_number=card_number,
                    card_data=card_json,
                    is_used=False
                )
                db.session.add(bingo_card)
                existing_cards.add(card_json)
                cards_generated += 1
                break
            
            attempts += 1
        
        if attempts >= 100:
            print(f"Warning: Could not generate unique card #{card_number}")
    
    try:
        db.session.commit()
        print(f"Successfully generated {cards_generated} unique bingo cards")
    except Exception as e:
        db.session.rollback()
        print(f"Error generating cards: {e}")

if __name__ == '__main__':
    from backend.app import app
    with app.app_context():
        generate_all_cards()
