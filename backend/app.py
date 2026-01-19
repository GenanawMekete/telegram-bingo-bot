from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import random
import secrets
from config import Config

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = Config.DATABASE_URL
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
CORS(app)

# Import models
from models import User, BingoCard, Game, PlayerGame, Transaction

@app.route('/')
def index():
    """Home endpoint."""
    return jsonify({
        'status': 'online',
        'service': 'Bingo Game API',
        'version': '1.0.0'
    })

@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})

@app.route('/api/user/<int:telegram_id>')
def get_user_info(telegram_id):
    """Get user information."""
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'telegram_id': user.telegram_id,
        'balance': float(user.balance),
        'games_played': user.games_played,
        'bingos': user.bingos,
        'total_won': float(user.total_won)
    })

@app.route('/api/cards')
def get_available_cards():
    """Get available bingo cards."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    cards = BingoCard.query.filter_by(is_used=False)\
        .order_by(BingoCard.card_number)\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'cards': [{
            'id': card.id,
            'card_number': card.card_number,
            'card_data': json.loads(card.card_data)
        } for card in cards.items],
        'total': cards.total,
        'page': cards.page,
        'per_page': cards.per_page,
        'pages': cards.pages
    })

@app.route('/api/cards/select', methods=['POST'])
def select_card():
    """Select a bingo card for a game."""
    data = request.json
    telegram_id = data.get('telegram_id')
    card_number = data.get('card_number')
    game_id = data.get('game_id')
    
    # Validate user
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check balance
    if user.balance < Config.CARD_PRICE:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Get card
    card = BingoCard.query.filter_by(card_number=card_number, is_used=False).first()
    if not card:
        return jsonify({'error': 'Card not available'}), 400
    
    # Get or create game
    game = None
    if game_id:
        game = Game.query.get(game_id)
    
    if not game:
        # Create new public game
        room_code = secrets.token_hex(3).upper()
        game = Game(room_code=room_code, status='waiting')
        db.session.add(game)
    
    # Deduct balance
    user.balance -= Config.CARD_PRICE
    game.prize_pool += Config.CARD_PRICE * (Config.PRIZE_POOL_PERCENTAGE / 100)
    
    # Create player game entry
    player_game = PlayerGame(
        game_id=game.id,
        user_id=user.id,
        card_number=card.card_number,
        card_data=card.card_data
    )
    db.session.add(player_game)
    
    # Mark card as used
    card.is_used = True
    
    # Add transaction
    transaction = Transaction(
        user_id=user.id,
        type='game_entry',
        amount=-Config.CARD_PRICE,
        description=f'Bingo card #{card_number}'
    )
    db.session.add(transaction)
    
    db.session.commit()
    
    # Emit player joined event
    socketio.emit('player_joined', {
        'user_id': user.id,
        'username': user.username or user.first_name,
        'room_code': game.room_code,
        'total_players': len(game.players)
    }, room=game.room_code)
    
    return jsonify({
        'success': True,
        'game_id': game.id,
        'room_code': game.room_code,
        'card': {
            'number': card.card_number,
            'data': json.loads(card.card_data)
        },
        'balance': float(user.balance)
    })

@app.route('/api/game/<int:game_id>')
def get_game_status(game_id):
    """Get game status."""
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    drawn_numbers = json.loads(game.drawn_numbers or '[]')
    
    return jsonify({
        'id': game.id,
        'room_code': game.room_code,
        'status': game.status,
        'drawn_numbers': drawn_numbers,
        'prize_pool': float(game.prize_pool),
        'players_count': len(game.players),
        'started_at': game.started_at.isoformat() if game.started_at else None
    })

@app.route('/api/game/<int:game_id>/draw', methods=['POST'])
def draw_number(game_id):
    """Draw a new number for the game."""
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    if game.status != 'active':
        return jsonify({'error': 'Game is not active'}), 400
    
    # Generate random number (1-75) that hasn't been drawn
    drawn_numbers = json.loads(game.drawn_numbers or '[]')
    
    if len(drawn_numbers) >= 75:
        return jsonify({'error': 'All numbers have been drawn'}), 400
    
    available_numbers = [n for n in range(1, 76) if n not in drawn_numbers]
    new_number = random.choice(available_numbers)
    
    drawn_numbers.append(new_number)
    game.drawn_numbers = json.dumps(drawn_numbers)
    db.session.commit()
    
    # Emit to all players in the room
    socketio.emit('number_drawn', {
        'number': new_number,
        'total_drawn': len(drawn_numbers)
    }, room=game.room_code)
    
    return jsonify({
        'number': new_number,
        'total_drawn': len(drawn_numbers)
    })

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('connected', {'status': 'connected'})

@socketio.on('join')
def handle_join(data):
    """Join a game room."""
    room = data.get('room_code')
    user_id = data.get('user_id')
    
    if room:
        join_room(room)
        emit('message', {
            'type': 'system',
            'message': f'User {user_id} joined room {room}'
        }, room=room)

@socketio.on('claim_bingo')
def handle_bingo_claim(data):
    """Handle bingo claim."""
    room = data.get('room_code')
    user_id = data.get('user_id')
    card_data = data.get('card_data')
    marked_numbers = data.get('marked_numbers')
    
    # Validate bingo (simplified)
    is_valid_bingo = validate_bingo(card_data, marked_numbers)
    
    if is_valid_bingo:
        # Get game and user
        game = Game.query.filter_by(room_code=room).first()
        user = User.query.filter_by(id=user_id).first()
        
        if game and user:
            # Update game status
            game.status = 'finished'
            game.winner_id = user.id
            game.finished_at = datetime.utcnow()
            
            # Award prize
            user.balance += game.prize_pool
            user.total_won += game.prize_pool
            user.games_played += 1
            user.bingos += 1
            
            # Record transaction
            transaction = Transaction(
                user_id=user.id,
                type='prize',
                amount=game.prize_pool,
                description=f'Bingo winner in room {room}'
            )
            db.session.add(transaction)
            
            db.session.commit()
            
            # Emit bingo event
            emit('bingo', {
                'winner_id': user.id,
                'winner_name': user.first_name,
                'prize_amount': float(game.prize_pool),
                'card_number': data.get('card_number')
            }, room=room)
    
    return {'valid': is_valid_bingo}

def validate_bingo(card_data, marked_numbers):
    """Validate if a bingo is legitimate."""
    # This is a simplified validation
    # In production, implement proper bingo pattern checking
    card = json.loads(card_data)
    marked = set(marked_numbers)
    
    # Check rows
    for row in card:
        if all(cell in marked or cell == 'FREE' for cell in row):
            return True
    
    # Check columns
    for col in range(5):
        if all(card[row][col] in marked or card[row][col] == 'FREE' for row in range(5)):
            return True
    
    # Check diagonals
    if all(card[i][i] in marked or card[i][i] == 'FREE' for i in range(5)):
        return True
    if all(card[i][4-i] in marked or card[i][4-i] == 'FREE' for i in range(5)):
        return True
    
    return False

if __name__ == '__main__':
    # Create database tables
    with app.app_context():
        db.create_all()
        
        # Generate cards if not exists
        from card_generator import generate_all_cards
        generate_all_cards()
    
    # Start server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
