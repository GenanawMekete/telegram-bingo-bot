import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackContext
import requests

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
BACKEND_URL = os.environ.get('BACKEND_URL', 'https://bingo-backend.onrender.com')

async def start(update: Update, context: CallbackContext):
    """Handle /start command."""
    user = update.effective_user
    
    # Register user with backend
    try:
        response = requests.post(f"{BACKEND_URL}/api/auth/login", json={
            'telegram_id': user.id,
            'first_name': user.first_name,
            'username': user.username
        })
        
        if response.status_code == 200:
            data = response.json()
            token = data['token']
            
            # Create WebApp button
            webapp_url = f"https://your-bingo.netlify.app?telegram_id={user.id}&auth={token}"
            
            keyboard = [[InlineKeyboardButton(
                "🎮 Play Bingo",
                web_app=WebAppInfo(url=webapp_url)
            )]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"Welcome {user.first_name}! 🎯\n\n"
                f"Click below to play Bingo:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ Error connecting to game server.")
            
    except Exception as e:
        logger.error(f"Start error: {e}")
        await update.message.reply_text("⚠️ Service temporarily unavailable.")

async def deposit(update: Update, context: CallbackContext):
    """Handle /deposit command."""
    await update.message.reply_text(
        "💳 To deposit funds, please contact support.\n"
        "This feature is currently in development."
    )

async def withdraw(update: Update, context: CallbackContext):
    """Handle /withdraw command."""
    await update.message.reply_text(
        "💰 To withdraw funds, please contact support.\n"
        "This feature is currently in development."
    )

async def balance(update: Update, context: CallbackContext):
    """Handle /balance command."""
    await update.message.reply_text(
        "📊 Please open the game to check your balance."
    )

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('deposit', deposit))
    application.add_handler(CommandHandler('withdraw', withdraw))
    application.add_handler(CommandHandler('balance', balance))
    
    print("🤖 Bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
