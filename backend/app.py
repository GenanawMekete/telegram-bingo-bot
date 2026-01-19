import os
import json
import random
import secrets
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, make_response
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import jwt
from functools import wraps

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///bingo.db').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', secrets.token_hex(32))
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

# Initialize extensions
db = SQLAlchemy(app)
socketio = SocketIO(app, 
                   cors_allowed_origins="*", 
                   async_mode='eventlet',
                   logger=True,
                   engineio_logger=True,
                   ping_timeout=60,
                   ping_interval=25)
CORS(app, resources={r"/*": {"origins": "*"}})

# Import models
from models import User, BingoCard, Game, PlayerGame, Transaction

# JWT Authentication Decorator
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
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# Generate JWT Token
def generate_token(user):
    token = jwt.encode({
        'user_id': user.id,
        'telegram_id': user.telegram_id,
        'exp': datetime.utcnow() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
    }, app.config['JWT_SECRET_KEY'], algorithm="HS256")
    return token

# Health check endpoint
@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'service': 'Bingo Game API',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'database': 'connected' if db.session.execute('SELECT 1').first() else 'disconnected',
        'timestamp': datetime.utcnow().isoformat()
    })

# User authentication
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    telegram_id = data.get('telegram_id')
    phone_number = data.get('phone_number')
    
    if not telegram_id and not phone_number:
        return jsonify({'error': 'Telegram ID or phone number required'}), 400
    
    user = None
    if telegram_id:
        user = User.query.filter_by(telegram_id=telegram_id).first()
    elif phone_number:
        user = User.query.filter_by(phone_number=phone_number).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate token
    token = generate_token(user)
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'telegram_id': user.telegram_id,
            'phone_number': user.phone_number,
            'username': user.username,
            'first_name': user.first_name,
            'balance': float(user.balance),
            'games_played': user.games_played,
            'bingos': user.bingos,
            'total_won': float(user.total_won)
        }
    })

@app.route('/api/auth/verify', methods=['POST'])
def verify():
    data = request.json
    phone_number = data.get('phone_number')
    verification_code = data.get('verification_code')
    
    if not phone_number or not verification_code:
        return jsonify({'error': 'Phone number and verification code required'}), 400
    
    user = User.query.filter_by(phone_number=phone_number).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.verification_code != verification_code:
        return jsonify({'error': 'Invalid verification code'}), 400
    
    # Mark as verified
    user.is_verified = True
    user.verification_code = None
    user.verified_at = datetime.utcnow()
    db.session.commit()
    
    # Generate token
    token = generate_token(user)
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'telegram_id': user.telegram_id,
            'phone_number': user.phone_number,
            'username': user.username,
            'first_name': user.first_name,
            'balance': float(user.balance)
        }
    })

# User endpoints
@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_user_profile(current_user):
    return jsonify({
        'id': current_user.id,
        'telegram_id': current_user.telegram_id,
        'phone_number': current_user.phone_number,
        'first_name': current_user.first_name,
        'last_name': current_user.last_name,
        'username': current_user.username,
        'balance': float(current_user.balance),
        'total_won': float(current_user.total_won),
        'games_played': current_user.games_played,
        'bingos': current_user.bingos,
        'is_verified': current_user.is_verified,
        'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
        'last_login': current_user.last_login.isoformat() if current_user.last_login else None
    })

@app.route('/api/user/transactions', methods=['GET'])
@token_required
def get_user_transactions(current_user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'transactions': [{
            'id': t.id,
            'type': t.type,
            'amount': float(t.amount),
            'description': t.description,
            'status': t.status,
            'created_at': t.created_at.isoformat() if t.created_at else None
        } for t in transactions.items],
        'total': transactions.total,
        'page': transactions.page,
        'per_page': transactions.per_page,
        'pages': transactions.pages
    })

# Card endpoints
@app.route('/api/cards', methods=['GET'])
@token_required
def get_available_cards(current_user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    game_id = request.args.get('game_id')
    
    # Check if user already has a card in this game
    if game_id:
        existing_card = PlayerGame.query.filter_by(
            game_id=game_id, 
            user_id=current_user.id
        ).first()
        if existing_card:
            return jsonify({
                'already_joined': True,
                'card': {
                    'id': existing_card.id,
                    'card_number': existing_card.card_number,
                    'card_data': json.loads(existing_card.card_data),
                    'marked_numbers': json.loads(existing_card.marked_numbers)
                }
            })
    
    cards = BingoCard.query.filter_by(is_used=False)\
        .order_by(BingoCard.card_number)\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'cards': [{
            'id': card.id,
            'card_number': card.card_number,
            'card_data': json.loads(card.card_data),
            'price': 5.00  # Fixed card price
        } for card in cards.items],
        'total': cards.total,
        'page': cards.page,
        'per_page': cards.per_page,
        'pages': cards.pages,
        'already_joined': False
    })

@app.route('/api/cards/select', methods=['POST'])
@token_required
def select_card(current_user):
    data = request.json
    card_number = data.get('card_number')
    game_id = data.get('game_id')
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
    if game_id:
        game = Game.query.get(game_id)
    elif room_code:
        game = Game.query.filter_by(room_code=room_code).first()
    
    if not game:
        # Create new public game
        room_code = secrets.token_hex(3).upper()
        game = Game(
            room_code=room_code,
            status='waiting',
            created_by=current_user.id
        )
        db.session.add(game)
        db.session.commit()
    
    # Check if game has started
    if game.status == 'active':
        return jsonify({'error': 'Game has already started'}), 400
    
    # Check if user already in game
    existing_entry = PlayerGame.query.filter_by(
        game_id=game.id,
        user_id=current_user.id
    ).first()
    if existing_entry:
        return jsonify({'error': 'Already joined this game'}), 400
    
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
        description=f'Bingo card #{card.card_number} for game {game.room_code}'
    )
    db.session.add(transaction)
    
    db.session.commit()
    
    # Emit player joined event
    socketio.emit('player_joined', {
        'user_id': current_user.id,
        'username': current_user.username or current_user.first_name,
        'telegram_id': current_user.telegram_id,
        'room_code': game.room_code,
        'player_count': len(game.players),
        'card_number': card.card_number
    }, room=game.room_code)
    
    return jsonify({
        'success': True,
        'game': {
            'id': game.id,
            'room_code': game.room_code,
            'status': game.status,
            'prize_pool': float(game.prize_pool),
            'player_count': len(game.players)
        },
        'card': {
            'number': card.card_number,
            'data': json.loads(card.card_data)
        },
        'balance': float(current_user.balance)
    })

# Game management
@app.route('/api/games', methods=['GET'])
@token_required
def get_games(current_user):
    status = request.args.get('status', 'waiting')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = Game.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    games = query.order_by(Game.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'games': [{
            'id': game.id,
            'room_code': game.room_code,
            'status': game.status,
            'prize_pool': float(game.prize_pool),
            'player_count': len(game.players),
            'created_by': game.created_by,
            'is_private': game.is_private,
            'created_at': game.created_at.isoformat() if game.created_at else None,
            'started_at': game.started_at.isoformat() if game.started_at else None
        } for game in games.items],
        'total': games.total,
        'page': games.page,
        'per_page': games.per_page,
        'pages': games.pages
    })

@app.route('/api/games/create', methods=['POST'])
@token_required
def create_game(current_user):
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
        'game': {
            'id': game.id,
            'room_code': game.room_code,
            'is_private': game.is_private,
            'created_at': game.created_at.isoformat()
        }
    })

@app.route('/api/games/<int:game_id>', methods=['GET'])
@token_required
def get_game(current_user, game_id):
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    # Check if user is in this game
    player_entry = PlayerGame.query.filter_by(
        game_id=game.id,
        user_id=current_user.id
    ).first()
    
    drawn_numbers = json.loads(game.drawn_numbers or '[]')
    
    return jsonify({
        'game': {
            'id': game.id,
            'room_code': game.room_code,
            'status': game.status,
            'drawn_numbers': drawn_numbers,
            'prize_pool': float(game.prize_pool),
            'player_count': len(game.players),
            'created_by': game.created_by,
            'is_private': game.is_private,
            'started_at': game.started_at.isoformat() if game.started_at else None,
            'finished_at': game.finished_at.isoformat() if game.finished_at else None
        },
        'players': [{
            'id': p.user.id,
            'username': p.user.username or p.user.first_name,
            'card_number': p.card_number,
            'has_bingo': p.has_bingo,
            'joined_at': p.joined_at.isoformat() if p.joined_at else None
        } for p in game.players],
        'my_entry': {
            'card_number': player_entry.card_number if player_entry else None,
            'card_data': json.loads(player_entry.card_data) if player_entry else None,
            'marked_numbers': json.loads(player_entry.marked_numbers) if player_entry else [],
            'has_bingo': player_entry.has_bingo if player_entry else False
        } if player_entry else None
    })

@app.route('/api/games/<int:game_id>/start', methods=['POST'])
@token_required
def start_game(current_user, game_id):
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    # Check if user is creator
    if game.created_by != current_user.id:
        return jsonify({'error': 'Only game creator can start the game'}), 403
    
    # Check if game can be started
    if game.status != 'waiting':
        return jsonify({'error': f'Game is already {game.status}'}), 400
    
    if len(game.players) < 2:
        return jsonify({'error': 'Need at least 2 players to start'}), 400
    
    # Start game
    game.status = 'active'
    game.started_at = datetime.utcnow()
    db.session.commit()
    
    # Emit game started event
    socketio.emit('game_started', {
        'room_code': game.room_code,
        'started_at': game.started_at.isoformat(),
        'player_count': len(game.players),
        'prize_pool': float(game.prize_pool)
    }, room=game.room_code)
    
    return jsonify({
        'success': True,
        'game': {
            'id': game.id,
            'room_code': game.room_code,
            'status': game.status,
            'started_at': game.started_at.isoformat()
        }
    })

@app.route('/api/games/<int:game_id>/draw', methods=['POST'])
@token_required
def draw_number_endpoint(current_user, game_id):
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    # Check if game is active
    if game.status != 'active':
        return jsonify({'error': 'Game is not active'}), 400
    
    # Check if user is creator or admin
    if game.created_by != current_user.id:
        return jsonify({'error': 'Only game creator can draw numbers'}), 403
    
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
        'total_drawn': len(drawn_numbers),
        'room_code': game.room_code,
        'drawn_by': current_user.id
    }, room=game.room_code)
    
    return jsonify({
        'number': new_number,
        'total_drawn': len(drawn_numbers)
    })

@app.route('/api/games/<int:game_id>/mark', methods=['POST'])
@token_required
def mark_number(current_user, game_id):
    data = request.json
    number = data.get('number')
    
    if not number:
        return jsonify({'error': 'Number required'}), 400
    
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    # Get player's card
    player_entry = PlayerGame.query.filter_by(
        game_id=game.id,
        user_id=current_user.id
    ).first()
    
    if not player_entry:
        return jsonify({'error': 'You are not in this game'}), 400
    
    # Check if number is on the card
    card_data = json.loads(player_entry.card_data)
    card_numbers = [item for sublist in card_data for item in sublist if item != 'FREE']
    
    if number not in card_numbers:
        return jsonify({'error': 'Number not on your card'}), 400
    
    # Add to marked numbers
    marked_numbers = json.loads(player_entry.marked_numbers or '[]')
    if number in marked_numbers:
        return jsonify({'error': 'Number already marked'}), 400
    
    marked_numbers.append(number)
    player_entry.marked_numbers = json.dumps(marked_numbers)
    db.session.commit()
    
    # Check for bingo
    if check_bingo(card_data, marked_numbers):
        player_entry.has_bingo = True
        db.session.commit()
        
        # Check if this is the first bingo
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
                description=f'Bingo winner in game {game.room_code}'
            )
            db.session.add(transaction)
            
            db.session.commit()
            
            # Emit bingo event
            socketio.emit('bingo', {
                'winner_id': current_user.id,
                'winner_name': current_user.username or current_user.first_name,
                'prize_amount': float(game.prize_pool),
                'card_number': player_entry.card_number,
                'is_first': True,
                'room_code': game.room_code
            }, room=game.room_code)
        else:
            # Subsequent bingo
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
        'has_bingo': player_entry.has_bingo
    })

def check_bingo(card_data, marked_numbers):
    """Check if a card has bingo."""
    # Convert card to 5x5 grid
    grid = card_data
    
    # Add FREE space to marked numbers
    effective_marked = list(marked_numbers) + ['FREE']
    
    # Check rows
    for row in range(5):
        if all(str(grid[row][col]) in effective_marked for col in range(5)):
            return True
    
    # Check columns
    for col in range(5):
        if all(str(grid[row][col]) in effective_marked for row in range(5)):
            return True
    
    # Check main diagonal
    if all(str(grid[i][i]) in effective_marked for i in range(5)):
        return True
    
    # Check anti-diagonal
    if all(str(grid[i][4-i]) in effective_marked for i in range(5)):
        return True
    
    # Check four corners (optional pattern)
    corners = [grid[0][0], grid[0][4], grid[4][0], grid[4][4]]
    if all(str(corner) in effective_marked for corner in corners):
        return True
    
    return False

# Wallet endpoints
@app.route('/api/wallet/balance', methods=['GET'])
@token_required
def get_balance(current_user):
    return jsonify({
        'balance': float(current_user.balance),
        'total_won': float(current_user.total_won),
        'games_played': current_user.games_played,
        'bingos': current_user.bingos
    })

@app.route('/api/wallet/deposit', methods=['POST'])
@token_required
def deposit_funds(current_user):
    data = request.json
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    # In production, integrate with payment gateway
    # For demo, just update balance
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
        'new_balance': float(current_user.balance),
        'transaction_id': transaction.id
    })

@app.route('/api/wallet/withdraw', methods=['POST'])
@token_required
def withdraw_funds(current_user):
    data = request.json
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    if current_user.balance < amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # In production, process withdrawal via payment gateway
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
        'new_balance': float(current_user.balance),
        'transaction_id': transaction.id
    })

# WebSocket events
@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'connected', 'sid': request.sid})

@socketio.on('join')
def handle_join(data):
    room = data.get('room_code')
    user_id = data.get('user_id')
    
    if room and user_id:
        join_room(room)
        emit('joined', {
            'room': room,
            'user_id': user_id,
            'message': f'User {user_id} joined room {room}'
        }, room=room)

@socketio.on('leave')
def handle_leave(data):
    room = data.get('room_code')
    if room:
        leave_room(room)
        emit('left', {'room': room}, room=room)

@socketio.on('chat_message')
def handle_chat_message(data):
    room = data.get('room_code')
    user_id = data.get('user_id')
    message = data.get('message')
    username = data.get('username')
    
    if room and message:
        emit('chat_message', {
            'user_id': user_id,
            'username': username,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Initialize database
def init_database():
    with app.app_context():
        db.create_all()
        print("Database tables created")
        
        # Generate cards if not exists
        from card_generator import generate_all_cards
        generate_all_cards()

if __name__ == '__main__':
    # Production vs development
    if os.environ.get('RENDER'):
        # Production on Render
        port = int(os.environ.get('PORT', 10000))
        print(f"Starting production server on port {port}")
        socketio.run(app, host='0.0.0.0', port=port)
    else:
        # Local development
        init_database()
        print("Starting development server on port 5000")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
