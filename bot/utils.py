import sqlite3
import secrets
import logging
from datetime import datetime
from config import Config

# Database connection
def get_db_connection():
    conn = sqlite3.connect('bingo.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            phone_number TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            balance REAL DEFAULT 10.00,
            verification_code TEXT,
            is_verified BOOLEAN DEFAULT FALSE,
            total_won REAL DEFAULT 0.00,
            games_played INTEGER DEFAULT 0,
            bingos INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create games table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'waiting',
            drawn_numbers TEXT DEFAULT '[]',
            prize_pool REAL DEFAULT 0.00,
            winner_id INTEGER,
            created_by INTEGER,
            is_private BOOLEAN DEFAULT FALSE,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create player_games table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            card_number INTEGER NOT NULL,
            card_data TEXT NOT NULL,
            marked_numbers TEXT DEFAULT '[]',
            has_bingo BOOLEAN DEFAULT FALSE,
            position INTEGER,
            prize_amount REAL DEFAULT 0.00,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create bingo_cards table (400 predefined cards)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bingo_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number INTEGER UNIQUE NOT NULL,
            card_data TEXT NOT NULL,
            is_used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully")

def get_user(telegram_id):
    """Get user by Telegram ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    
    conn.close()
    
    if user:
        return dict(user)
    return None

def create_user(telegram_id, phone_number, first_name, last_name="", username="", verification_code=""):
    """Create a new user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users 
            (telegram_id, phone_number, first_name, last_name, username, verification_code)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (telegram_id, phone_number, first_name, last_name, username, verification_code))
        
        conn.commit()
        user_id = cursor.lastrowid
        
        # Add initial bonus transaction
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, 'bonus', 10.00, 'Welcome bonus')
        ''', (user_id,))
        
        conn.commit()
        
        logging.info(f"Created new user: {telegram_id}")
        return user_id
        
    except sqlite3.IntegrityError:
        logging.warning(f"User already exists: {telegram_id}")
        return None
    finally:
        conn.close()

def update_balance(telegram_id, amount, transaction_type):
    """Update user balance and record transaction."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users 
        SET balance = balance + ?
        WHERE telegram_id = ?
    ''', (amount, telegram_id))
    
    # Get user_id for transaction record
    cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    
    if user:
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount)
            VALUES (?, ?, ?)
        ''', (user['id'], transaction_type, amount))
    
    conn.commit()
    conn.close()
    
    logging.info(f"Updated balance for {telegram_id}: {amount}")

def add_transaction(user_id, transaction_type, amount, description=""):
    """Add a transaction record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, description)
        VALUES (?, ?, ?, ?)
    ''', (user_id, transaction_type, amount, description))
    
    conn.commit()
    conn.close()

def generate_verification_code():
    """Generate a 6-digit verification code."""
    return secrets.randbelow(900000) + 100000

def get_active_games():
    """Get list of active games."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT g.*, COUNT(pg.id) as players 
        FROM games g
        LEFT JOIN player_games pg ON g.id = pg.game_id
        WHERE g.status IN ('waiting', 'active')
        GROUP BY g.id
        ORDER BY g.created_at DESC
    ''')
    
    games = cursor.fetchall()
    conn.close()
    
    return [dict(game) for game in games]

def create_game(room_code, created_by, is_private=False):
    """Create a new game."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO games (room_code, created_by, is_private)
        VALUES (?, ?, ?)
    ''', (room_code, created_by, is_private))
    
    game_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return game_id
