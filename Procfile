web: gunicorn run:app --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 --keep-alive 5
bot: python bot/bot.py
