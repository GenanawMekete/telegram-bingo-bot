"""
Telegram Bingo Backend API
Production-ready with Gevent WebSocket support
"""

import os
import sys
import json
import random
import secrets
import logging
from datetime import datetime, timedelta
from functools import wraps

# Gevent monkey patch - MUST BE FIRST
from gevent import monkey
monkey.patch_all()

# Now import Flask and other modules
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import jwt

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.environ.get('RENDER') else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='../webapp')

# ========== CONFIGURATION ==========
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///bingo.db').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', secrets.token_hex(32))
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

# ========== EXTENSIONS ==========
db = SQLAlchemy(app)

# Configure SocketIO for production/development
is_production = os.environ.get('RENDER') is not None

if is_production:
    # Production settings for Render
    socketio = SocketIO(app,
                       cors_allowed_origins="*",
                       async_mode='gevent',
                       ping_timeout=300,
                       ping_interval=60,
                       logger=False,
                       engineio_logger=False,
                       transports=['websocket', 'polling'],
                       allow_upgrades=True,
                       max_http_buffer_size=1e8)
else:
    # Development settings
    socketio = SocketIO(app,
                       cors_allowed_origins="*",
                       async_mode='gevent',
                       debug=True,
                       logger=True,
                       engineio_logger=True)

CORS(app, resources={
    r"/api/*": {"origins": "*"},
    r"/socket.io/*": {"origins": "*"}
})

# ========== DATABASE MODELS ==========
class User(db.Model):
    """User model for Telegram users."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    phone_number = db.Column(db.String(20), unique=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    username = db.Column(db.String(100))
    balance = db.Column(db.Float, default=10.00)
    verification_code = db.Column(db.String(10))
    is_verified = db.Column(db.Boolean, default=False)
    total_won = db.Column(db.Float, default=0.00)
    games_played = db.Column(db.Integer, default=0)
    bingos = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    player_games = db.relationship('PlayerGame', backref='player', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'phone_number': self.phone_number,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'username': self.username,
            'balance': float(self.balance),
            'is_verified': self.is_verified,
            'total_won': float(self.total_won),
            'games_played': self.games_played,
            'bingos': self.bingos,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class BingoCard(db.Model):
    """Predefined bingo cards (400 cards)."""
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
            'card_data': json.loads(self.card_data) if self.card_data else [],
            'is_used': self.is_used,
            'price': 5.00
        }

class Game(db.Model):
    """Game session model."""
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(10), unique=True, nullable=False)
    status = db.Column(db.String(20), default='waiting')
    drawn_numbers = db.Column(db.Text, default='[]')
    prize_pool = db.Column(db.Float, default=0.00)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_private = db.Column(db.Boolean, default=False)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    players = db.relationship('PlayerGame', backref='game', lazy=True)
    winner = db.relationship('User', foreign_keys=[winner_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def to_dict(self):
        drawn_numbers = json.loads(self.drawn_numbers) if self.drawn_numbers else []
        return {
            'id': self.id,
            'room_code': self.room_code,
            'status': self.status,
            'drawn_numbers': drawn_numbers,
            'prize_pool': float(self.prize_pool),
            'player_count': len(self.players),
            'created_by': self.created_by,
            'is_private': self.is_private,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class PlayerGame(db.Model):
    """Association between players and games."""
    __tablename__ = 'player_games'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_number = db.Column(db.Integer, nullable=False)
    card_data = db.Column(db.Text, nullable=False)
    marked_numbers = db.Column(db.Text, default='[]')
    has_bingo = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer)
    prize_amount = db.Column(db.Float, default=0.00)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'game_id': self.game_id,
            'user_id': self.user_id,
            'card_number': self.card_number,
            'card_data': json.loads(self.card_data) if self.card_data else [],
            'marked_numbers': json.loads(self.marked_numbers) if self.marked_numbers else [],
            'has_bingo': self.has_bingo,
            'prize_amount': float(self.prize_amount),
            'joined_at': self.joined_at.isoformat() if self.joined_at else None
        }

class Transaction(db.Model):
    """Transaction model."""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'amount': float(self.amount),
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# ========== JWT AUTHENTICATION ==========
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token is missing', 'code': 'TOKEN_MISSING'}), 401
        
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired', 'code': 'TOKEN_EXPIRED'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token', 'code': 'TOKEN_INVALID'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

def generate_token(user):
    token = jwt.encode({
        'user_id': user.id,
        'telegram_id': user.telegram_id,
        'exp': datetime.utcnow() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
    }, app.config['JWT_SECRET_KEY'], algorithm="HS256")
    return token

# ========== HELPER FUNCTIONS ==========
def check_bingo(card_data, marked_numbers):
    """Check if a card has bingo."""
    if not card_data or not marked_numbers:
        return False
    
    # Add FREE space to marked numbers
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

# ========== STATIC FILE SERVING ==========
@app.route('/')
def serve_frontend():
    """Serve the frontend for Telegram Mini App."""
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except:
        return jsonify({
            'status': 'backend_active',
            'message': 'Bingo Backend API is running',
            'version': '1.0.0',
            'timestamp': datetime.utcnow().isoformat()
        })

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files for frontend."""
    return send_from_directory(app.static_folder, path)

# ========== API ROUTES ==========

# Health check
@app.route('/api/health')
def health():
    """Health check endpoint."""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        db_status = 'connected'
    except Exception as e:
        db_status = f'disconnected: {str(e)}'
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'service': 'Bingo Game API',
        'timestamp': datetime.utcnow().isoformat(),
        'environment': 'production' if is_production else 'development'
    })

# Authentication
@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login with Telegram ID."""
    data = request.json
    telegram_id = data.get('telegram_id')
    
    if not telegram_id:
        return jsonify({'error': 'Telegram ID required', 'code': 'TELEGRAM_ID_REQUIRED'}), 400
    
    user = User.query.filter_by(telegram_id=telegram_id).first()
    
    if not user:
        # Create new user
        user = User(
            telegram_id=telegram_id,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            username=data.get('username', ''),
            phone_number=data.get('phone_number', ''),
            balance=10.00  # Starting bonus
        )
        db.session.add(user)
        
        # Add welcome bonus transaction
        transaction = Transaction(
            user_id=user.id,
            type='bonus',
            amount=10.00,
            description='Welcome bonus'
        )
        db.session.add(transaction)
        db.session.commit()
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate token
    token = generate_token(user)
    
    return jsonify({
        'token': token,
        'user': user.to_dict()
    })

# User endpoints
@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_user_profile(current_user):
    """Get current user profile."""
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    })

@app.route('/api/user/balance', methods=['GET'])
@token_required
def get_balance(current_user):
    """Get user balance."""
    return jsonify({
        'success': True,
        'balance': float(current_user.balance),
        'total_won': float(current_user.total_won)
    })

# Card endpoints
@app.route('/api/cards', methods=['GET'])
@token_required
def get_available_cards(current_user):
    """Get available bingo cards."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    game_id = request.args.get('game_id')
    
    # Check if user already has a card in this game
    if game_id:
        existing = PlayerGame.query.filter_by(
            game_id=game_id,
            user_id=current_user.id
        ).first()
        if existing:
            return jsonify({
                'already_joined': True,
                'card': existing.to_dict()
            })
    
    # Get available cards
    cards = BingoCard.query.filter_by(is_used=False)\
        .order_by(BingoCard.card_number)\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'cards': [card.to_dict() for card in cards.items],
        'total': cards.total,
        'page': cards.page,
        'per_page': cards.per_page,
        'pages': cards.pages,
        'already_joined': False
    })

@app.route('/api/cards/select', methods=['POST'])
@token_required
def select_card(current_user):
    """Select a bingo card for a game."""
    data = request.json
    card_number = data.get('card_number')
    game_id = data.get('game_id')
    room_code = data.get('room_code')
    
    if not card_number:
        return jsonify({'error': 'Card number required', 'code': 'CARD_NUMBER_REQUIRED'}), 400
    
    # Check balance
    CARD_PRICE = 5.00
    if current_user.balance < CARD_PRICE:
        return jsonify({'error': 'Insufficient balance', 'code': 'INSUFFICIENT_BALANCE'}), 400
    
    # Get card
    card = BingoCard.query.filter_by(card_number=card_number, is_used=False).first()
    if not card:
        return jsonify({'error': 'Card not available', 'code': 'CARD_NOT_AVAILABLE'}), 400
    
    # Get or create game
    game = None
    if game_id:
        game = Game.query.get(game_id)
    elif room_code:
        game = Game.query.filter_by(room_code=room_code).first()
    
    if not game:
        # Create new public game
        room_code = secrets.token_hex(3).upper()
        game = Game(
            room_code=room_code,
            created_by=current_user.id,
            status='waiting'
        )
        db.session.add(game)
        db.session.commit()
    
    # Check if game has started
    if game.status == 'active':
        return jsonify({'error': 'Game has already started', 'code': 'GAME_STARTED'}), 400
    
    # Check if user already in game
    existing = PlayerGame.query.filter_by(
        game_id=game.id,
        user_id=current_user.id
    ).first()
    if existing:
        return jsonify({'error': 'Already joined this game', 'code': 'ALREADY_JOINED'}), 400
    
    # Deduct balance
    current_user.balance -= CARD_PRICE
    game.prize_pool += CARD_PRICE * 0.8  # 80% to prize pool
    
    # Create player game entry
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
        description=f'Bingo card #{card.card_number}'
    )
    db.session.add(transaction)
    
    db.session.commit()
    
    # Notify room
    socketio.emit('player_joined', {
        'user_id': current_user.id,
        'username': current_user.username or current_user.first_name,
        'room_code': game.room_code,
        'player_count': len(game.players),
        'card_number': card.card_number
    }, room=game.room_code)
    
    return jsonify({
        'success': True,
        'game': game.to_dict(),
        'card': card.to_dict(),
        'balance': float(current_user.balance)
    })

# Game management
@app.route('/api/games', methods=['GET'])
@token_required
def get_games(current_user):
    """Get available games."""
    status = request.args.get('status', 'waiting')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query = Game.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    games = query.order_by(Game.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'games': [game.to_dict() for game in games.items],
        'total': games.total,
        'page': games.page,
        'per_page': games.per_page,
        'pages': games.pages
    })

@app.route('/api/games/create', methods=['POST'])
@token_required
def create_game(current_user):
    """Create a new game room."""
    data = request.json
    is_private = data.get('is_private', False)
    
    room_code = secrets.token_hex(3).upper()
    
    game = Game(
        room_code=room_code,
        created_by=current_user.id,
        is_private=is_private
    )
    db.session.add(game)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'game': game.to_dict()
    })

@app.route('/api/games/<int:game_id>', methods=['GET'])
@token_required
def get_game(current_user, game_id):
    """Get game details."""
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found', 'code': 'GAME_NOT_FOUND'}), 404
    
    player_entry = PlayerGame.query.filter_by(
        game_id=game.id,
        user_id=current_user.id
    ).first()
    
    players = []
    for pg in game.players:
        player = User.query.get(pg.user_id)
        if player:
            players.append({
                'id': player.id,
                'username': player.username or player.first_name,
                'card_number': pg.card_number,
                'has_bingo': pg.has_bingo
            })
    
    return jsonify({
        'success': True,
        'game': game.to_dict(),
        'players': players,
        'my_entry': player_entry.to_dict() if player_entry else None
    })

@app.route('/api/games/<int:game_id>/start', methods=['POST'])
@token_required
def start_game(current_user, game_id):
    """Start a game."""
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found', 'code': 'GAME_NOT_FOUND'}), 404
    
    # Check permissions
    if game.created_by != current_user.id:
        return jsonify({'error': 'Only game creator can start', 'code': 'NOT_CREATOR'}), 403
    
    if game.status != 'waiting':
        return jsonify({'error': f'Game is already {game.status}', 'code': 'GAME_NOT_WAITING'}), 400
    
    if len(game.players) < 2:
        return jsonify({'error': 'Need at least 2 players', 'code': 'NOT_ENOUGH_PLAYERS'}), 400
    
    # Start game
    game.status = 'active'
    game.started_at = datetime.utcnow()
    db.session.commit()
    
    # Notify players
    socketio.emit('game_started', {
        'room_code': game.room_code,
        'started_at': game.started_at.isoformat(),
        'player_count': len(game.players),
        'prize_pool': float(game.prize_pool)
    }, room=game.room_code)
    
    return jsonify({
        'success': True,
        'game': game.to_dict()
    })

@app.route('/api/games/<int:game_id>/draw', methods=['POST'])
@token_required
def draw_number_endpoint(current_user, game_id):
    """Draw a number for the game."""
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found', 'code': 'GAME_NOT_FOUND'}), 404
    
    # Check permissions
    if game.created_by != current_user.id:
        return jsonify({'error': 'Only game creator can draw numbers', 'code': 'NOT_CREATOR'}), 403
    
    if game.status != 'active':
        return jsonify({'error': 'Game is not active', 'code': 'GAME_NOT_ACTIVE'}), 400
    
    # Get drawn numbers
    drawn_numbers = json.loads(game.drawn_numbers or '[]')
    
    if len(drawn_numbers) >= 75:
        return jsonify({'error': 'All numbers drawn', 'code': 'ALL_NUMBERS_DRAWN'}), 400
    
    # Draw new number
    available_numbers = [n for n in range(1, 76) if n not in drawn_numbers]
    new_number = random.choice(available_numbers)
    
    drawn_numbers.append(new_number)
    game.drawn_numbers = json.dumps(drawn_numbers)
    db.session.commit()
    
    # Notify players
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
    """Mark a number on player's card."""
    data = request.json
    number = data.get('number')
    
    if not number:
        return jsonify({'error': 'Number required', 'code': 'NUMBER_REQUIRED'}), 400
    
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found', 'code': 'GAME_NOT_FOUND'}), 404
    
    # Get player's card
    player_entry = PlayerGame.query.filter_by(
        game_id=game.id,
        user_id=current_user.id
    ).first()
    
    if not player_entry:
        return jsonify({'error': 'Not in this game', 'code': 'NOT_IN_GAME'}), 400
    
    # Check if number is on card
    card_data = json.loads(player_entry.card_data)
    card_numbers = []
    for row in card_data:
        for cell in row:
            if cell != 'FREE':
                card_numbers.append(int(cell))
    
    if int(number) not in card_numbers:
        return jsonify({'error': 'Number not on card', 'code': 'NUMBER_NOT_ON_CARD'}), 400
    
    # Mark number
    marked_numbers = json.loads(player_entry.marked_numbers or '[]')
    if int(number) in marked_numbers:
        return jsonify({'error': 'Number already marked', 'code': 'NUMBER_ALREADY_MARKED'}), 400
    
    marked_numbers.append(int(number))
    player_entry.marked_numbers = json.dumps(marked_numbers)
    
    # Check for bingo
    has_bingo = check_bingo(card_data, marked_numbers)
    player_entry.has_bingo = has_bingo
    
    db.session.commit()
    
    if has_bingo:
        # Check if first bingo
        other_bingos = PlayerGame.query.filter_by(
            game_id=game.id,
            has_bingo=True
        ).filter(PlayerGame.user_id != current_user.id).count()
        
        if other_bingos == 0:
            # First bingo - game ends
            game.status = 'finished'
            game.winner_id = current_user.id
            game.finished_at = datetime.utcnow()
            
            # Award prize
            current_user.balance += game.prize_pool
            current_user.total_won += game.prize_pool
            current_user.games_played += 1
            current_user.bingos += 1
            
            # Record transaction
            transaction = Transaction(
                user_id=current_user.id,
                type='prize',
                amount=game.prize_pool,
                description=f'Bingo winner in room {game.room_code}'
            )
            db.session.add(transaction)
            
            db.session.commit()
            
            # Notify players
            socketio.emit('bingo', {
                'winner_id': current_user.id,
                'winner_name': current_user.username or current_user.first_name,
                'prize_amount': float(game.prize_pool),
                'card_number': player_entry.card_number,
                'is_first': True,
                'room_code': game.room_code
            }, room=game.room_code)
        else:
            # Notify about bingo (but not winner)
            socketio.emit('bingo', {
                'winner_id': current_user.id,
                'winner_name': current_user.username or current_user.first_name,
                'prize_amount': 0,
                'card_number': player_entry.card_number,
                'is_first': False,
                'room_code': game.room_code
            }, room=game.room_code)
    
    return jsonify({
        'success': True,
        'marked_numbers': marked_numbers,
        'has_bingo': has_bingo
    })

# Wallet endpoints
@app.route('/api/wallet/deposit', methods=['POST'])
@token_required
def deposit_funds(current_user):
    """Deposit funds (simulated)."""
    data = request.json
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Invalid amount', 'code': 'INVALID_AMOUNT'}), 400
    
    # In production, integrate with payment gateway
    current_user.balance += amount
    
    transaction = Transaction(
        user_id=current_user.id,
        type='deposit',
        amount=amount,
        description='Manual deposit'
    )
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_balance': float(current_user.balance)
    })

@app.route('/api/wallet/withdraw', methods=['POST'])
@token_required
def withdraw_funds(current_user):
    """Withdraw funds (simulated)."""
    data = request.json
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Invalid amount', 'code': 'INVALID_AMOUNT'}), 400
    
    if current_user.balance < amount:
        return jsonify({'error': 'Insufficient balance', 'code': 'INSUFFICIENT_BALANCE'}), 400
    
    current_user.balance -= amount
    
    transaction = Transaction(
        user_id=current_user.id,
        type='withdrawal',
        amount=-amount,
        description='Manual withdrawal'
    )
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_balance': float(current_user.balance)
    })

# ========== WEBSOCKET EVENTS ==========
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {
        'status': 'connected',
        'sid': request.sid,
        'timestamp': datetime.utcnow().isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnect."""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('join')
def handle_join(data):
    """Join a game room."""
    room = data.get('room_code')
    user_id = data.get('user_id')
    
    if room and user_id:
        join_room(room)
        logger.info(f"User {user_id} joined room {room}")
        
        # Get user info
        user = User.query.get(user_id)
        if user:
            username = user.username or user.first_name
        else:
            username = f"User{user_id}"
        
        emit('player_joined_ws', {
            'user_id': user_id,
            'username': username,
            'room': room,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room)

@socketio.on('leave')
def handle_leave(data):
    """Leave a game room."""
    room = data.get('room_code')
    if room:
        leave_room(room)
        emit('player_left', {'room': room}, room=room)

@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat messages."""
    room = data.get('room_code')
    user_id = data.get('user_id')
    message = data.get('message')
    
    if room and message and user_id:
        # Get user info
        user = User.query.get(user_id)
        username = user.username or user.first_name if user else f"User{user_id}"
        
        emit('chat_message', {
            'user_id': user_id,
            'username': username,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room)

# ========== ERROR HANDLERS ==========
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not found',
        'message': 'The requested resource was not found',
        'code': 'NOT_FOUND'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred',
        'code': 'INTERNAL_ERROR'
    }), 500

@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        'error': 'Bad request',
        'message': 'The request was malformed or invalid',
        'code': 'BAD_REQUEST'
    }), 400

# ========== DATABASE INITIALIZATION ==========
def init_database():
    """Initialize database tables."""
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created/verified")
            
            # Generate cards if none exist
            from card_generator import generate_all_cards
            card_count = BingoCard.query.count()
            if card_count == 0:
                logger.info("Generating 400 bingo cards...")
                generate_all_cards()
                logger.info(f"Generated {BingoCard.query.count()} bingo cards")
            else:
                logger.info(f"Database already has {card_count} bingo cards")
                
        except Exception as e:
            logger.error(f"Database initialization error: {e}")

# ========== APPLICATION ENTRY POINT ==========
if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Run the application
    logger.info(f"Starting Bingo backend server on port {port}")
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=not is_production,
        allow_unsafe_werkzeug=True
    )
