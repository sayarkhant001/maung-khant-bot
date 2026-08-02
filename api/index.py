"""
Vercel Python entrypoint — Flask app routing all API requests.
  POST/GET /api/webhook  → Telegram bot webhook
  GET      /api/cron     → Daily cron job
"""
import os
import sys
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
    except Exception as e:
        print(f"Webhook error: {e}")
    return jsonify({"ok": True})


# ─── Cron ─────────────────────────────────────────────────────────────────────

@app.route("/api/cron", methods=["GET"])
def cron():
    from api.cron import run_cron, CRON_SECRET
    secret = request.headers.get("x-cron-secret", "")
    if CRON_SECRET and secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(run_cron())


# ─── Health check ─────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok"})


# Vercel Python runtime entry point
handler = app
