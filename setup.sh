#!/bin/bash
echo "🛠️ Setting up database..."
python -c "
from backend.app import app, db
with app.app_context():
    db.create_all()
    print('✅ Tables created')
    
    from backend.models import BingoCard
    if BingoCard.query.count() == 0:
        print('🃏 Generating cards...')
        from backend.app import generate_card
        import json
        
        existing_cards = set()
        for card_number in range(1, 401):
            for _ in range(50):
                card = generate_card()
                card_json = json.dumps(card)
                if card_json not in existing_cards:
                    bingo_card = BingoCard(
                        card_number=card_number,
                        card_data=card_json,
                        is_used=False
                    )
                    db.session.add(bingo_card)
                    existing_cards.add(card_json)
                    break
        db.session.commit()
        print(f'✅ Generated {BingoCard.query.count()} cards')
    else:
        print(f'✅ Already have {BingoCard.query.count()} cards')
"
echo "🎉 Setup complete!"
