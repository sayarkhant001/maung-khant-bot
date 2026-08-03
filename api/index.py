"""
Vercel Python entrypoint — Flask app routing all API requests.
  POST/GET /api/webhook  → Telegram bot webhook
  GET      /api/cron     → Daily cron job
  GET      /api/debug    → Diagnostics
"""
import os
import sys
import traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, request, jsonify
import telebot

app = Flask(__name__)

# ─── Webhook ──────────────────────────────────────────────────────────────────

@app.route("/api/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return jsonify({"status": "ok", "bot": "@maungkhantsbot running"})
    try:
        from api.webhook import get_bot
        update_dict = request.get_json(force=True, silent=True) or {}
        update = telebot.types.Update.de_json(update_dict)
        get_bot().process_new_updates([update])
        return jsonify({"ok": True})
    except Exception as e:
        err = traceback.format_exc()
        print(f"Webhook error: {err}")
        return jsonify({"ok": False, "error": str(e)}), 200  # 200 so Telegram doesn't retry


# ─── Cron ─────────────────────────────────────────────────────────────────────

@app.route("/api/cron", methods=["GET"])
def cron():
    from api.cron import run_cron, CRON_SECRET
    secret = request.headers.get("x-cron-secret", "")
    if CRON_SECRET and secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(run_cron())


# ─── Debug ────────────────────────────────────────────────────────────────────

@app.route("/api/debug", methods=["GET"])
def debug():
    result = {}

    # 1. Check raw env vars
    result["env_BOT_TOKEN"]    = "SET" if os.getenv("BOT_TOKEN") else "MISSING"
    result["env_ADMIN_ID"]     = "SET" if os.getenv("ADMIN_ID") else "MISSING"
    result["env_SPREADSHEET"]  = "SET" if os.getenv("GOOGLE_SPREADSHEET_ID") else "MISSING"
    result["env_SA_JSON"]      = "SET" if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64") else "MISSING"

    # 2. Load config
    try:
        from lib import config
        result["config"] = "OK"
        result["bot_token_prefix"] = config.BOT_TOKEN[:8] + "..."
        result["admin_id"] = config.ADMIN_ID
    except Exception as e:
        result["config_error"] = str(e)
        result["config_trace"] = traceback.format_exc()
        return jsonify(result)

    # 3. Init bot
    try:
        from api.webhook import get_bot
        bot = get_bot()
        result["bot_init"] = "OK"
    except Exception as e:
        result["bot_init_error"] = str(e)
        result["bot_init_trace"] = traceback.format_exc()
        return jsonify(result)

    # 4. Test Telegram API
    try:
        me = bot.get_me()
        result["bot_username"] = me.username
        result["telegram_api"] = "OK"
    except Exception as e:
        result["telegram_error"] = str(e)

    # 5. Test Google Sheets
    try:
        from lib import sheets
        ws = sheets.get_sheet("users")
        result["sheets"] = "OK"
    except Exception as e:
        result["sheets_error"] = str(e)

    return jsonify(result)


# ─── Health check ─────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok"})


# Vercel Python runtime entry point
handler = app
