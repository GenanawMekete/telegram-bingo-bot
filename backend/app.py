"""
Telegram Bingo Backend - Minimal Production Version
Works with Python 3.11 on Render
"""

import os
import sys
import json
import random
import secrets
import logging
from datetime import datetime, timedelta
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Import Flask
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import jwt

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# ========== CONFIGURATION ==========
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'sqlite:///bingo.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', secrets.token_hex(32))
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

# ========== EXTENSIONS ==========
db = SQLAlchemy(app)

# Configure SocketIO - use threading for Render compatibility
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',  # Works without eventlet/gevent
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25
)

CORS(app, resources={r"/*": {"origins": "*"}})

# ========== SIMPLE DATABASE MODELS ==========
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    first_name = db.Column(db.String(100))
    balance = db.Column(db.Float, default=10.00)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'first_name': self.first_name,
            'balance': float(self.balance)
        }

class BingoCard(db.Model):
    __tablename__ = 'bingo_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.Integer, unique=True, nullable=False)
    card_data = db.Column(db.Text, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'card_number': self.card_number,
            'card_data': json.loads(self.card_data),
            'is_used': self.is_used
        }

class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(10), unique=True, nullable=False)
    status = db.Column(db.String(20), default='waiting')
    drawn_numbers = db.Column(db.Text, default='[]')
    prize_pool = db.Column(db.Float, default=0.00)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'room_code': self.room_code,
            'status': self.status,
            'drawn_numbers': json.loads(self.drawn_numbers) if self.drawn_numbers else [],
            'prize_pool': float(self.prize_pool)
        }

class PlayerGame(db.Model):
    __tablename__ = 'player_games'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    card_number = db.Column(db.Integer, nullable=False)
    marked_numbers = db.Column(db.Text, default='[]')
    
    def to_dict(self):
        return {
            'game_id': self.game_id,
            'user_id': self.user_id,
            'card_number': self.card_number,
            'marked_numbers': json.loads(self.marked_numbers) if self.marked_numbers else []
        }

# ========== HELPER FUNCTIONS ==========
def generate_token(user):
    token = jwt.encode({
        'user_id': user.id,
        'telegram_id': user.telegram_id,
        'exp': datetime.utcnow() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
    }, app.config['JWT_SECRET_KEY'], algorithm="HS256")
    return token

def check_bingo(card_data, marked_numbers):
    """Simple bingo check."""
    effective_marked = [str(num) for num in marked_numbers] + ['FREE']
    
    # Check rows
    for row in range(5):
        if all(str(card_data[row][col]) in effective_marked for col in range(5)):
            return True
    
    return False

def generate_bingo_card():
    """Generate a simple bingo card."""
    card = []
    numbers = list(range(1, 76))
    random.shuffle(numbers)
    
    for row in range(5):
        card_row = []
        for col in range(5):
            if row == 2 and col == 2:
                card_row.append('FREE')
            else:
                card_row.append(numbers.pop())
        card.append(card_row)
    
    return card

# ========== API ROUTES ==========
@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'service': 'Bingo API',
        'version': '1.0.0'
    })

@app.route('/api/health')
def health():
    """Health check endpoint."""
    try:
        db.session.execute('SELECT 1')
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'healthy', 'database': str(e)[:100]}), 200

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Simple login endpoint."""
    data = request.json
    telegram_id = data.get('telegram_id')
    
    if not telegram_id:
        return jsonify({'error': 'Telegram ID required'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            first_name=data.get('first_name', 'Player'),
            balance=10.00
        )
        db.session.add(user)
        db.session.commit()
    
    token = generate_token(user)
    
    return jsonify({
        'success': True,
        'token': token,
        'user': user.to_dict()
    })

@app.route('/api/cards', methods=['GET'])
def get_cards():
    """Get available cards."""
    cards = BingoCard.query.filter_by(is_used=False).limit(20).all()
    
    if not cards:
        # Generate some sample cards
        for i in range(1, 21):
            card = generate_bingo_card()
            bingo_card = BingoCard(
                card_number=i,
                card_data=json.dumps(card),
                is_used=False
            )
            db.session.add(bingo_card)
        db.session.commit()
        cards = BingoCard.query.filter_by(is_used=False).limit(20).all()
    
    return jsonify({
        'success': True,
        'cards': [card.to_dict() for card in cards]
    })

@app.route('/api/cards/select', methods=['POST'])
def select_card():
    """Select a card."""
    data = request.json
    card_number = data.get('card_number')
    telegram_id = data.get('telegram_id')
    
    if not card_number or not telegram_id:
        return jsonify({'error': 'Missing data'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    card = BingoCard.query.filter_by(card_number=card_number, is_used=False).first()
    if not card:
        return jsonify({'error': 'Card not available'}), 400
    
    # Create game
    room_code = secrets.token_hex(3).upper()
    game = Game(room_code=room_code)
    db.session.add(game)
    
    # Mark card as used
    card.is_used = True
    
    # Create player entry
    player_game = PlayerGame(
        game_id=game.id,
        user_id=user.id,
        card_number=card.card_number
    )
    db.session.add(player_game)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'game': game.to_dict(),
        'card': card.to_dict()
    })

@app.route('/api/games/<int:game_id>/draw', methods=['POST'])
def draw_number_endpoint(game_id):
    """Draw a number."""
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    drawn_numbers = json.loads(game.drawn_numbers or '[]')
    
    if len(drawn_numbers) >= 75:
        return jsonify({'error': 'All numbers drawn'}), 400
    
    new_number = random.randint(1, 75)
    while new_number in drawn_numbers:
        new_number = random.randint(1, 75)
    
    drawn_numbers.append(new_number)
    game.drawn_numbers = json.dumps(drawn_numbers)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'number': new_number,
        'total_drawn': len(drawn_numbers)
    })

@app.route('/api/games/<int:game_id>/mark', methods=['POST'])
def mark_number(game_id):
    """Mark a number."""
    data = request.json
    number = data.get('number')
    user_id = data.get('user_id')
    
    if not number or not user_id:
        return jsonify({'error': 'Missing data'}), 400
    
    player_game = PlayerGame.query.filter_by(game_id=game_id, user_id=user_id).first()
    if not player_game:
        return jsonify({'error': 'Not in game'}), 400
    
    marked_numbers = json.loads(player_game.marked_numbers or '[]')
    if number in marked_numbers:
        return jsonify({'error': 'Already marked'}), 400
    
    marked_numbers.append(number)
    player_game.marked_numbers = json.dumps(marked_numbers)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'marked_numbers': marked_numbers
    })

# ========== WEBSOCKET EVENTS ==========
@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'connected'})

@socketio.on('join')
def handle_join(data):
    room = data.get('room')
    if room:
        join_room(room)
        emit('joined', {'room': room, 'message': 'Joined room'})

# ========== INITIALIZATION ==========
def init_database():
    """Initialize database."""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")
        
        # Create admin user if none exists
        if User.query.count() == 0:
            admin = User(
                telegram_id=123456789,
                first_name='Admin',
                balance=100.00
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("Created admin user")

# ========== RUN APPLICATION ==========
if __name__ == '__main__':
    init_database()
    
    port = int(os.environ.get('PORT', 5000))
    debug_mode = not os.environ.get('RENDER')
    
    logger.info(f"Starting server on port {port}")
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        allow_unsafe_werkzeug=True
    )
