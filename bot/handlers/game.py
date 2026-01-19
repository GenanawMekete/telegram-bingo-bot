from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import CallbackContext
from utils import get_user, get_active_games, create_game as db_create_game
import secrets
from config import Config

async def play(update: Update, context: CallbackContext):
    """Send button to open the Bingo WebApp."""
    user = update.effective_user
    db_user = get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please register first with /start")
        return
    
    if db_user['balance'] < Config.CARD_PRICE:
        await update.message.reply_text(
            f"❌ Insufficient balance!\n"
            f"Card price: ${Config.CARD_PRICE:.2f}\n"
            f"Your balance: ${db_user['balance']:.2f}\n\n"
            "Use /deposit to add funds."
        )
        return
    
    # Create WebApp button
    webapp_url = f"{Config.WEBAPP_URL}?user_id={user.id}&auth={secrets.token_urlsafe(16)}"
    button = InlineKeyboardButton(
        "🎮 Play Bingo Now!",
        web_app=WebAppInfo(url=webapp_url)
    )
    
    keyboard = InlineKeyboardMarkup([[button]])
    
    await update.message.reply_text(
        f"🎯 Bingo Game Lobby\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 Balance: ${db_user['balance']:.2f}\n"
        f"🎫 Card Price: ${Config.CARD_PRICE:.2f}\n"
        f"🏆 Prize Pool: 80% of all entries\n\n"
        f"Click below to select your card and join the game:",
        reply_markup=keyboard
    )

async def create_game(update: Update, context: CallbackContext):
    """Create a private game room."""
    user = update.effective_user
    db_user = get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please register first with /start")
        return
    
    # Generate unique room code
    room_code = secrets.token_hex(3).upper()
    
    # Create game in database
    game_id = db_create_game(
        room_code=room_code,
        created_by=user.id,
        is_private=True
    )
    
    # Create invite link
    invite_link = f"https://t.me/{Config.BOT_USERNAME}?start=room_{room_code}"
    
    await update.message.reply_text(
        f"🎉 Private Game Room Created!\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏷️ Room Code: {room_code}\n"
        f"🔗 Invite Link: {invite_link}\n\n"
        f"Share this code with friends to play together!\n\n"
        f"Use /play to join the game once everyone is ready."
    )
