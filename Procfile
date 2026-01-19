web: gunicorn run:app --worker-class gevent --bind 0.0.0.0:$PORT --timeout 120 --keep-alive 5 --worker-connections 1000 --log-level info
bot: python bot/bot.py
