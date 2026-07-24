"""
Main Telegram Webhook — receives all updates from Telegram.
Registered at: POST /api/webhook
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

import telebot

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.handlers import user, buy, gift, admin
from lib.handlers import admin_manual_order, admin_plans, admin_payments, admin_reports

# ─── Lazy Bot Init ────────────────────────────────────────────────────────────
# Bot is created on first request to avoid errors at import time
_bot = None


def get_bot() -> telebot.TeleBot:
    global _bot
    if _bot is None:
        _bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode=None)

        # Register all handlers — order matters (most specific first)
        admin_manual_order.register(_bot)   # admin_renewed_ + /manual_order
        admin_plans.register(_bot)           # zoom/canva plan management
        admin_payments.register(_bot)        # payment methods management
        admin_reports.register(_bot)         # reports + CSV export
        admin.register(_bot)                # main admin panel
        buy.register(_bot)                  # Zoom/Canva buy flow
        gift.register(_bot)                 # coupon redemption
        user.register(_bot)                 # /start, menus, subscriptions

        # "Stop Reminders" from cron alert buttons
        @_bot.callback_query_handler(func=lambda c: c.data.startswith("admin_stop_renewal_"))
        def cb_stop_renewal(call: telebot.types.CallbackQuery):
            if call.from_user.id != config.ADMIN_ID:
                return
            sub_id = call.data.replace("admin_stop_renewal_", "")
            from lib import sheets
            sheets.deactivate_manual_renewal(sub_id)
            _bot.answer_callback_query(call.id, f"Reminders stopped for {sub_id}.")
            try:
                _bot.edit_message_reply_markup(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=None,
                )
            except Exception:
                pass

    return _bot


# ─── Vercel Handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            update_dict = json.loads(body.decode("utf-8"))
            update = telebot.types.Update.de_json(update_dict)
            get_bot().process_new_updates([update])
        except Exception as e:
            print(f"Webhook error: {e}")
        self._respond(200, {"ok": True})

    def do_GET(self):
        self._respond(200, {"status": "ok", "bot": "@maungkhantsbot running"})

    def _respond(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
