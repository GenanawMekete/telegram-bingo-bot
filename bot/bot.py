import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    CallbackContext, ConversationHandler
)
from handlers.start import start, phone_received
from handlers.wallet import deposit, withdraw, balance
from handlers.game import play, create_game
from config import Config
from utils import init_db, get_user, create_user

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
PHONE = 1

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Log errors."""
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    """Start the bot."""
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Conversation handler for phone verification
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, phone_received)],
        },
        fallbacks=[]
    )
    
    # Register command handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('deposit', deposit))
    application.add_handler(CommandHandler('withdraw', withdraw))
    application.add_handler(CommandHandler('balance', balance))
    application.add_handler(CommandHandler('play', play))
    application.add_handler(CommandHandler('create', create_game))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    print("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
