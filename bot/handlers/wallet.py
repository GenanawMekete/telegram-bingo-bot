from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, CallbackQueryHandler
from utils import get_user, update_balance, add_transaction
from config import Config

async def deposit(update: Update, context: CallbackContext):
    """Handle deposit command."""
    user = update.effective_user
    db_user = get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please register first with /start")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("$10", callback_data="deposit_10"),
            InlineKeyboardButton("$25", callback_data="deposit_25"),
            InlineKeyboardButton("$50", callback_data="deposit_50"),
        ],
        [
            InlineKeyboardButton("$100", callback_data="deposit_100"),
            InlineKeyboardButton("Custom Amount", callback_data="deposit_custom"),
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"💳 Deposit Funds\n"
        f"Current balance: ${db_user['balance']:.2f}\n"
        f"Minimum deposit: ${Config.DEPOSIT_MIN:.2f}\n\n"
        "Select amount or choose custom:",
        reply_markup=reply_markup
    )

async def withdraw(update: Update, context: CallbackContext):
    """Handle withdrawal command."""
    user = update.effective_user
    db_user = get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please register first with /start")
        return
    
    if db_user['balance'] < Config.WITHDRAWAL_MIN:
        await update.message.reply_text(
            f"❌ Minimum withdrawal is ${Config.WITHDRAWAL_MIN:.2f}\n"
            f"Your balance: ${db_user['balance']:.2f}"
        )
        return
    
    # In production, you would integrate with a payment gateway
    # For now, simulate withdrawal
    amount = min(db_user['balance'], 50.00)  # Max $50 for demo
    
    update_balance(user.id, -amount, 'withdrawal')
    add_transaction(user.id, 'withdrawal', -amount, f"Withdrawal to bank account")
    
    await update.message.reply_text(
        f"✅ Withdrawal request processed!\n"
        f"Amount: ${amount:.2f}\n"
        f"New balance: ${db_user['balance'] - amount:.2f}\n\n"
        "Note: This is a simulation. In production, integrate with a payment gateway."
    )

async def balance(update: Update, context: CallbackContext):
    """Show user balance."""
    user = update.effective_user
    db_user = get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please register first with /start")
        return
    
    await update.message.reply_text(
        f"💰 Account Balance\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Available: ${db_user['balance']:.2f}\n"
        f"Total Won: ${db_user.get('total_won', 0):.2f}\n"
        f"Games Played: {db_user.get('games_played', 0)}\n"
        f"Bingos: {db_user.get('bingos', 0)}"
    )

async def deposit_callback(update: Update, context: CallbackContext):
    """Handle deposit callback queries."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if data == "deposit_custom":
        await query.edit_message_text(
            "Please enter the deposit amount (e.g., 15.50):\n"
            f"Minimum: ${Config.DEPOSIT_MIN:.2f}"
        )
        # Set state for custom amount
        return
    
    # Process predefined amounts
    amounts = {
        "deposit_10": 10.00,
        "deposit_25": 25.00,
        "deposit_50": 50.00,
        "deposit_100": 100.00
    }
    
    if data in amounts:
        amount = amounts[data]
        update_balance(user.id, amount, 'deposit')
        add_transaction(user.id, 'deposit', amount, "Telegram deposit")
        
        db_user = get_user(user.id)
        
        await query.edit_message_text(
            f"✅ Deposit successful!\n"
            f"Amount: ${amount:.2f}\n"
            f"New balance: ${db_user['balance']:.2f}\n\n"
            "Note: This is a simulation. In production, integrate with a payment gateway."
        )
