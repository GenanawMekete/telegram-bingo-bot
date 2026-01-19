import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bingo_bot")
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bingo.db")
    
    # WebApp Configuration
    WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-webapp.vercel.app")
    BACKEND_URL = os.getenv("BACKEND_URL", "https://your-backend.vercel.app")
    
    # Game Configuration
    MAX_PLAYERS = 100
    CARD_PRICE = 5.00  # $5 per card
    PRIZE_POOL_PERCENTAGE = 80  # 80% of entry fees go to prize pool
    
    # Session Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # Payment Configuration (Simulated for now)
    DEPOSIT_MIN = 10.00
    WITHDRAWAL_MIN = 20.00
    
    # Telegram WebApp Data
    WEBAPP_TITLE = "Telegram Bingo"
    WEBAPP_SHORT_NAME = "BingoGame"
    WEBAPP_DESCRIPTION = "Play multiplayer Bingo with friends!"
