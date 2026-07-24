"""
Local development runner — uses polling instead of webhook.
Only use this for LOCAL TESTING. Do NOT run this while Vercel webhook is active.

Usage:
    pip install -r requirements.txt
    python run_local.py

The bot (@maungkhantsbot) will respond to messages via polling.
Stop with Ctrl+C.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Verify env is set before importing anything
missing = []
for var in ["BOT_TOKEN", "ADMIN_ID", "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64", "GOOGLE_SPREADSHEET_ID"]:
    if not os.getenv(var) or os.getenv(var, "").startswith("PASTE_"):
        missing.append(var)

if missing:
    print("❌ Missing environment variables in .env:")
    for v in missing:
        print(f"   - {v}")
    print("\nEdit .env and fill in the required values first.")
    sys.exit(1)

import telebot
from lib import config
from lib.handlers import user, buy, gift, admin
from lib.handlers import admin_manual_order, admin_plans, admin_payments, admin_reports

print(f"Starting bot @maungkhantsbot (ID: {config.BOT_TOKEN[:10]}...)")
print(f"   Admin ID: {config.ADMIN_ID}")
print(f"   Support: {config.SUPPORT_USERNAME}")
print("   Mode: POLLING (local dev)")
print("   Press Ctrl+C to stop\n")

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode=None)

# Register all handlers
admin_manual_order.register(bot)
admin_plans.register(bot)
admin_payments.register(bot)
admin_reports.register(bot)
admin.register(bot)
buy.register(bot)
gift.register(bot)
user.register(bot)

# Stop Reminders handler
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_stop_renewal_"))
def cb_stop_renewal(call):
    if call.from_user.id != config.ADMIN_ID:
        return
    sub_id = call.data.replace("admin_stop_renewal_", "")
    from lib import sheets
    sheets.deactivate_manual_renewal(sub_id)
    bot.answer_callback_query(call.id, f"Reminders stopped for {sub_id}.")

print("🤖 Bot is running... Send /start to @maungkhantsbot on Telegram\n")
bot.infinity_polling(timeout=30, long_polling_timeout=20)
