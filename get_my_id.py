"""
Run this to find your Telegram user ID.
1. Send any message to @maungkhantsbot on Telegram first
2. Then run:  python get_my_id.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

import telebot
token = os.environ["BOT_TOKEN"]
bot = telebot.TeleBot(token)
updates = bot.get_updates(limit=5, offset=-5)
if not updates:
    print("No updates found. Send /start to @maungkhantsbot on Telegram first, then run again.")
else:
    print("Recent senders:")
    for u in updates:
        msg = u.message or u.callback_query
        if msg:
            user = getattr(msg, 'from_user', None) or getattr(msg, 'from_', None)
            if user:
                print(f"  ID: {user.id}  |  @{user.username}  |  {user.first_name}")
    print("\nAdd your ID to ADMIN_ID= in .env")
