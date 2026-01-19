# 🎯 Telegram Multiplayer Bingo Game

A fully-featured multiplayer Bingo game that runs inside Telegram as a Mini App.

## ✨ Features

- **Telegram Mini App**: Play directly in Telegram on mobile and desktop
- **Multiplayer**: Real-time games with up to 100 players
- **400 Predefined Cards**: Unique bingo cards for variety
- **Wallet System**: Deposit, withdraw, and check balance
- **Phone Verification**: Secure user authentication
- **Private Rooms**: Create and share private game rooms
- **Real-time Updates**: WebSocket-powered live game updates
- **Responsive Design**: Works on all devices

## 🏗️ Architecture

- **Telegram Bot**: Python bot handling commands and user interaction
- **Flask Backend**: REST API + WebSocket server for game logic
- **Frontend WebApp**: HTML/CSS/JS interface for Telegram Mini App
- **SQLite Database**: Local database (upgradable to PostgreSQL)

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.9+
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- Vercel and Render accounts (free tiers available)

### 2. Local Setup
```bash
# Clone and setup
git clone <repository-url>
cd telegram-bingo-bot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your bot token

# Initialize database
python database/init_db.py

# Start backend server
cd backend && python app.py

# In another terminal, start the bot
python bot/bot.py
