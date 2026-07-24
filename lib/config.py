import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@support")

# ─── Google Sheets ────────────────────────────────────────────────────────────
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON_BASE64"]
GOOGLE_SPREADSHEET_ID = os.environ["GOOGLE_SPREADSHEET_ID"]

# ─── Outline VPN (optional) ───────────────────────────────────────────────────
OUTLINE_SERVER_API = os.getenv("OUTLINE_SERVER_API", "")

# ─── Operational Settings ─────────────────────────────────────────────────────
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "3"))
VPN_ORDER_EXPIRY_HOURS = int(os.getenv("VPN_ORDER_EXPIRY_HOURS", "24"))
MANUAL_ORDER_EXPIRY_HOURS = int(os.getenv("MANUAL_ORDER_EXPIRY_HOURS", "72"))

# Reminder thresholds (days remaining)
VPN_TIME_REMINDERS = [5, 3, 1, 0]
VPN_GB_REMINDERS = [75, 85, 95, 100]  # percentage thresholds
