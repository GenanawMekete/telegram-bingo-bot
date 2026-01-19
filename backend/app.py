"""
Telegram Bingo Backend - Production Ready
Simplified for Render deployment
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

# Configure SocketIO without eventlet/gevent for Render
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',  # Use threading instead of eventlet/gevent
    logger=True,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25
)

CORS(app, resources={r"/*": {"origins": "*"}})

# ========== DATABASE MODELS ==========
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    first_name = db.Column(db.String(100))
    username = db.Column(db.String(100))
    balance = db.Column(db.Float, default=10.00)
    total_won = db.Column(db.Float, default=0.00)
    games_played = db.Column(db.Integer, default=0)
    bingos = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'first_name': self.first_name,
            'username': self.username,
            'balance': float(self.balance),
            'total_won': float(self.total_won),
            'games_played': self.games_played,
            'bingos': self.bingos
        }

class BingoCard(db.Model):
    __tablename__ = 'bingo_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.Integer, unique=True, nullable=False)
    card_data = db.Column(db.Text, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_by = db.Column(db.Integer)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'room_code': self.room_code,
            'status': self.status,
            'drawn_numbers': json.loads(self.drawn_numbers) if self.drawn_numbers else [],
            'prize_pool': float(self.prize_pool),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class PlayerGame(db.Model):
    __tablename__ = 'player_games'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    card_number = db.Column(db.Integer, nullable=False)
    card_data = db.Column(db.Text, nullable=False)
    marked_numbers = db.Column(db.Text, default='[]')
    has_bingo = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'game_id': self.game_id,
            'user_id': self.user_id,
            'card_number': self.card_number,
            'card_data': json.loads(self.card_data),
            'marked_numbers': json.loads(self.marked_numbers),
            'has_bingo': self.has_bingo
        }

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'amount': float(self.amount),
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# ========== HELPER FUNCTIONS ==========
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

def generate_token(user):
    token = jwt.encode({
        'user_id': user.id,
        'telegram_id': user.telegram_id,
        'exp': datetime.utcnow() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
    }, app.config['JWT_SECRET_KEY'], algorithm="HS256")
    return token

def check_bingo(card_data, marked_numbers):
    """Check for bingo pattern."""
    effective_marked = [str(num) for num in marked_numbers] + ['FREE']
    
    # Check rows
    for row in range(5):
        if all(str(card_data[row][col]) in effective_marked for col in range(5)):
            return True
    
    # Check columns
    for col in range(5):
        if all(str(card_data[row][col]) in effective_marked for row in range(5)):
            return True
    
    # Check diagonals
    if all(str(card_data[i][i]) in effective_marked for i in range(5)):
        return True
    if all(str(card_data[i][4-i]) in effective_marked for i in range(5)):
        return True
    
    return False

def generate_card():
    """Generate a single bingo card."""
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
    
    card[2][2] = 'FREE'  # Middle cell
    return card

# ========== API ROUTES ==========
@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'service': 'Bingo API',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/health')
def health():
    """Health check endpoint."""
    try:
        db.session.execute('SELECT 1')
        db_status = 'connected'
    except:
        db_status = 'disconnected'
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login."""
    data = request.json
    telegram_id = data.get('telegram_id')
    
    if not telegram_id:
        return jsonify({'error': 'Telegram ID required'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            first_name=data.get('first_name', 'User'),
            username=data.get('username', ''),
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

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_user_profile(current_user):
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    })

@app.route('/api/cards', methods=['GET'])
@token_required
def get_available_cards(current_user):
    """Get available cards."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    cards = BingoCard.query.filter_by(is_used=False)\
        .order_by(BingoCard.card_number)\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'cards': [card.to_dict() for card in cards.items],
        'total': cards.total,
        'page': cards.page,
        'pages': cards.pages
    })

@app.route('/api/cards/select', methods=['POST'])
@token_required
def select_card(current_user):
    """Select a bingo card."""
    data = request.json
    card_number = data.get('card_number')
    room_code = data.get('room_code')
    
    if not card_number:
        return jsonify({'error': 'Card number required'}), 400
    
    # Check balance
    CARD_PRICE = 5.00
    if current_user.balance < CARD_PRICE:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Get card
    card = BingoCard.query.filter_by(card_number=card_number, is_used=False).first()
    if not card:
        return jsonify({'error': 'Card not available'}), 400
    
    # Get or create game
    game = None
    if room_code:
        game = Game.query.filter_by(room_code=room_code).first()
    
    if not game:
        room_code = secrets.token_hex(3).upper()
        game = Game(room_code=room_code, created_by=current_user.id)
        db.session.add(game)
    
    # Check if already joined
    existing = PlayerGame.query.filter_by(game_id=game.id, user_id=current_user.id).first()
    if existing:
        return jsonify({'error': 'Already in game'}), 400
    
    # Deduct balance
    current_user.balance -= CARD_PRICE
    game.prize_pool += CARD_PRICE * 0.8
    
    # Create player entry
    player_game = PlayerGame(
        game_id=game.id,
        user_id=current_user.id,
        card_number=card.card_number,
        card_data=card.card_data
    )
    db.session.add(player_game)
    
    # Mark card as used
    card.is_used = True
    
    # Add transaction
    transaction = Transaction(
        user_id=current_user.id,
        type='game_entry',
        amount=-CARD_PRICE,
        description=f'Card #{card_number}'
    )
    db.session.add(transaction)
    
    db.session.commit()
    
    # Emit WebSocket event
    socketio.emit('player_joined', {
        'user_id': current_user.id,
        'username': current_user.first_name,
        'room_code': game.room_code,
        'card_number': card.card_number
    }, room=game.room_code)
    
    return jsonify({
        'success': True,
        'game': game.to_dict(),
        'card': card.to_dict(),
        'balance': float(current_user.balance)
    })

@app.route('/api/games', methods=['GET'])
@token_required
def get_games(current_user):
    """Get available games."""
    status = request.args.get('status', 'waiting')
    
    query = Game.query
    if status != 'all':
        query = query.filter_by(status=status)
    
    games = query.order_by(Game.created_at.desc()).limit(20).all()
    
    return jsonify({
        'success': True,
        'games': [game.to_dict() for game in games]
    })

@app.route('/api/games/<int:game_id>/draw', methods=['POST'])
@token_required
def draw_number_endpoint(current_user, game_id):
    """Draw a number."""
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    if game.status != 'active':
        return jsonify({'error': 'Game not active'}), 400
    
    drawn_numbers = json.loads(game.drawn_numbers or '[]')
    
    if len(drawn_numbers) >= 75:
        return jsonify({'error': 'All numbers drawn'}), 400
    
    available = [n for n in range(1, 76) if n not in drawn_numbers]
    new_number = random.choice(available)
    
    drawn_numbers.append(new_number)
    game.drawn_numbers = json.dumps(drawn_numbers)
    db.session.commit()
    
    # Emit WebSocket event
    socketio.emit('number_drawn', {
        'number': new_number,
        'total_drawn': len(drawn_numbers),
        'room_code': game.room_code
    }, room=game.room_code)
    
    return jsonify({
        'success': True,
        'number': new_number,
        'total_drawn': len(drawn_numbers)
    })

@app.route('/api/games/<int:game_id>/mark', methods=['POST'])
@token_required
def mark_number(current_user, game_id):
    """Mark a number on card."""
    data = request.json
    number = data.get('number')
    
    if not number:
        return jsonify({'error': 'Number required'}), 400
    
    # Get player's card
    player_game = PlayerGame.query.filter_by(game_id=game_id, user_id=current_user.id).first()
    if not player_game:
        return jsonify({'error': 'Not in game'}), 400
    
    marked_numbers = json.loads(player_game.marked_numbers or '[]')
    if number in marked_numbers:
        return jsonify({'error': 'Already marked'}), 400
    
    marked_numbers.append(number)
    player_game.marked_numbers = json.dumps(marked_numbers)
    
    # Check for bingo
    card_data = json.loads(player_game.card_data)
    if check_bingo(card_data, marked_numbers):
        player_game.has_bingo = True
        
        # Check if first bingo
        game = Game.query.get(game_id)
        other_bingos = PlayerGame.query.filter_by(
            game_id=game_id,
            has_bingo=True
        ).filter(PlayerGame.user_id != current_user.id).count()
        
        if other_bingos == 0:
            # Winner
            game.status = 'finished'
            game.finished_at = datetime.utcnow()
            
            current_user.balance += game.prize_pool
            current_user.total_won += game.prize_pool
            current_user.games_played += 1
            current_user.bingos += 1
            
            # Emit WebSocket event
            socketio.emit('bingo', {
                'winner_id': current_user.id,
                'winner_name': current_user.first_name,
                'prize_amount': float(game.prize_pool),
                'room_code': game.room_code
            }, room=game.room_code)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'marked_numbers': marked_numbers,
        'has_bingo': player_game.has_bingo
    })

# ========== WEBSOCKET EVENTS ==========
@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'connected', 'timestamp': datetime.utcnow().isoformat()})

@socketio.on('join')
def handle_join(data):
    room = data.get('room_code')
    user_id = data.get('user_id')
    
    if room and user_id:
        join_room(room)
        user = User.query.get(user_id)
        username = user.first_name if user else f'User{user_id}'
        
        emit('player_joined_ws', {
            'user_id': user_id,
            'username': username,
            'room': room
        }, room=room)

@socketio.on('chat_message')
def handle_chat_message(data):
    room = data.get('room_code')
    message = data.get('message')
    user_id = data.get('user_id')
    
    if room and message:
        user = User.query.get(user_id)
        username = user.first_name if user else f'User{user_id}'
        
        emit('chat_message', {
            'username': username,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room)

# ========== INITIALIZATION ==========
def init_database():
    """Initialize database and generate cards."""
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")
        
        # Generate 400 cards if none exist
        if BingoCard.query.count() == 0:
            logger.info("Generating bingo cards...")
            cards_generated = 0
            existing_cards = set()
            
            for card_number in range(1, 401):
                for _ in range(50):  # Try 50 times max
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
                        cards_generated += 1
                        break
            
            db.session.commit()
            logger.info(f"Generated {cards_generated} bingo cards")
        else:
            logger.info(f"Database already has {BingoCard.query.count()} cards")

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
        allow_unsafe_werkzeug=True,
        use_reloader=False
    )
