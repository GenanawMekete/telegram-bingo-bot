import os
import logging
import requests
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BACKEND_URL = os.environ.get("BACKEND_URL", "https://telegram-bingo-bot-r9lg.onrender.com")

# Your real Render URL
RENDER_URL = "https://bingo-bot-9ue0.onrender.com"
WEBHOOK_PATH = "/telegram"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

app = FastAPI()

# Telegram Application
application = Application.builder().token(BOT_TOKEN).build()


# ---------------- HANDLERS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    try:
        # ⚠️ Blocking requests in async → run safely
        response = requests.post(f"{BACKEND_URL}/api/auth/login", json={
            "telegram_id": user.id,
            "first_name": user.first_name,
            "username": user.username
        }, timeout=10)

        if response.status_code == 200:
            data = response.json()
            token = data["token"]

            webapp_url = f"https://darling-beijinho-d1609d.netlify.app?telegram_id={user.id}&auth={token}"

            keyboard = [[InlineKeyboardButton(
                "🎮 Play Bingo",
                web_app=WebAppInfo(url=webapp_url)
            )]]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"Welcome {user.first_name}! 🎯\n\nClick below to play Bingo:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ Error connecting to game server.")

    except Exception as e:
        logger.error(f"Start error: {e}")
        await update.message.reply_text("⚠️ Service temporarily unavailable.")


async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💳 Deposit feature coming soon.")


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 Withdraw feature coming soon.")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Please open the game to check your balance.")


# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("deposit", deposit))
application.add_handler(CommandHandler("withdraw", withdraw))
application.add_handler(CommandHandler("balance", balance))


# ---------------- WEBHOOK ENDPOINT ---------------- #

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False}


# ---------------- STARTUP EVENT ---------------- #

@app.on_event("startup")
async def startup():
    # VERY IMPORTANT: initialize the app
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook set to: {WEBHOOK_URL}")
