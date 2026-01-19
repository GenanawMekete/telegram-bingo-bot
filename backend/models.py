from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from backend.app import db

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    player_games = db.relationship('PlayerGame', backref='player', lazy=True)
    
    def __repr__(self):
        return f'<User {self.telegram_id}>'

class BingoCard(db.Model):
    """Predefined bingo cards (400 cards)."""
    __tablename__ = 'bingo_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.Integer, unique=True, nullable=False)
    card_data = db.Column(db.Text, nullable=False)  # JSON string
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BingoCard #{self.card_number}>'

class Game(db.Model):
    """Game session model."""
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(10), unique=True, nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, active, finished
    drawn_numbers = db.Column(db.Text, default='[]')  # JSON array
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
    
    def __repr__(self):
        return f'<Game {self.room_code}>'

class PlayerGame(db.Model):
    """Association between players and games."""
    __tablename__ = 'player_games'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_number = db.Column(db.Integer, nullable=False)
    card_data = db.Column(db.Text, nullable=False)  # JSON string
    marked_numbers = db.Column(db.Text, default='[]')  # JSON array
    has_bingo = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer)
    prize_amount = db.Column(db.Float, default=0.00)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PlayerGame user:{self.user_id} game:{self.game_id}>'

class Transaction(db.Model):
    """Transaction model for deposits, withdrawals, and game fees."""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, game_entry, prize, bonus
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Transaction {self.type} ${self.amount}>'
