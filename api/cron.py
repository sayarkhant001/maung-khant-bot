"""
Cron job logic — exposes run_cron() and CRON_SECRET.
Called by api/index.py (Flask entrypoint) at GET /api/cron.
Runs daily at 3:00 AM UTC (9:30 AM Myanmar time).
Tasks:
  1. Expire old unsubmitted orders
  2. Send expiry reminders to subscribers (5d, 3d, 1d, 0d)
  3. Send 41/42-day manual renewal alerts to admin
"""
import os
from datetime import datetime

import telebot

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config, sheets
from lib.messages import EXPIRY_REMINDER, EXPIRY_REMINDER_0, MANUAL_RENEWAL_REMINDER

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode=None)

CRON_SECRET = os.getenv("CRON_SECRET", "")  # optional security header


def run_cron() -> dict:
    results = {
        "expired_orders": 0,
        "expiry_reminders_sent": 0,
        "manual_renewal_alerts": 0,
        "errors": [],
    }

    # ── 1. Expire old pending orders ──────────────────────────────────────────
    try:
        sheets.expire_old_orders()
        results["expired_orders"] = 1  # just marks done
    except Exception as e:
        results["errors"].append(f"expire_orders: {e}")

    # ── 2. Subscription expiry reminders to users ─────────────────────────────
    try:
        subs = sheets.get_all_active_subscriptions()
        now = datetime.utcnow()

        for sub in subs:
            try:
                expiry_str = sub.get("expiry_date", "")
                if not expiry_str:
                    continue
                exp = datetime.strptime(str(expiry_str)[:19], "%Y-%m-%d %H:%M:%S")
                days_left = (exp - now).days
                chat_id = int(sub.get("chat_id") or sub.get("user_id"))
                sub_id = sub.get("id", "")
                product = sub.get("product_type", "subscription")

                sent = False

                if days_left == 0 and str(sub.get("reminder_0day_sent", "")).upper() != "TRUE":
                    bot.send_message(
                        chat_id,
                        EXPIRY_REMINDER_0.format(product=product),
                        parse_mode="Markdown",
                    )
                    sheets.update_subscription(sub_id, reminder_0day_sent="TRUE")
                    sheets.expire_subscription(sub_id)
                    sheets.deactivate_manual_renewal(sub_id)
                    sent = True

                elif days_left in (1,) and str(sub.get("reminder_1day_sent", "")).upper() != "TRUE":
                    bot.send_message(
                        chat_id,
                        EXPIRY_REMINDER.format(product=product, days=days_left),
                        parse_mode="Markdown",
                    )
                    sheets.update_subscription(sub_id, reminder_1day_sent="TRUE")
                    sent = True

                elif days_left in (3,) and str(sub.get("reminder_3day_sent", "")).upper() != "TRUE":
                    bot.send_message(
                        chat_id,
                        EXPIRY_REMINDER.format(product=product, days=days_left),
                        parse_mode="Markdown",
                    )
                    sheets.update_subscription(sub_id, reminder_3day_sent="TRUE")
                    sent = True

                elif days_left == 5 and str(sub.get("reminder_3day_sent", "")).upper() != "TRUE":
                    bot.send_message(
                        chat_id,
                        EXPIRY_REMINDER.format(product=product, days=days_left),
                        parse_mode="Markdown",
                    )
                    sent = True

                if sent:
                    results["expiry_reminders_sent"] += 1

            except Exception as e:
                results["errors"].append(f"reminder sub {sub.get('id')}: {e}")

    except Exception as e:
        results["errors"].append(f"expiry_reminders: {e}")

    # ── 3. 42-day manual renewal alerts to ADMIN ──────────────────────────────
    try:
        due = sheets.get_manual_renewals_due()

        for r in due:
            sub_id = r.get("sub_id", "")
            user_id = r.get("user_id", "")
            username = r.get("username", "N/A")
            product = r.get("product_type", "")
            plan = r.get("plan_name", "")
            expiry_str = str(r.get("expiry_date", ""))[:10]

            try:
                exp_dt = datetime.strptime(expiry_str, "%Y-%m-%d")
                days_left = (exp_dt - datetime.utcnow()).days
            except Exception:
                days_left = "?"

            from lib.bot_helpers import admin_main_keyboard
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(
                telebot.types.InlineKeyboardButton(
                    "✅ Mark as Renewed",
                    callback_data=f"admin_renewed_{sub_id}"
                )
            )
            markup.add(
                telebot.types.InlineKeyboardButton(
                    "🔕 Stop Reminders",
                    callback_data=f"admin_stop_renewal_{sub_id}"
                )
            )

            bot.send_message(
                config.ADMIN_ID,
                MANUAL_RENEWAL_REMINDER.format(
                    username=username,
                    user_id=user_id,
                    product=product,
                    plan_name=plan,
                    sub_id=sub_id,
                    expiry=expiry_str,
                    days_left=days_left,
                ),
                parse_mode="Markdown",
                reply_markup=markup,
            )

            plan_days = 0
            try:
                plan_name = r.get("plan_name", "")
                product = str(r.get("product_type", "")).lower()
                plan_sheet = "zoom_plans" if "zoom" in product else "canva_plans"
                plans = sheets._sheet_to_dicts(sheets.get_sheet(plan_sheet))
                match = next((p for p in plans if p.get("name") == plan_name), None)
                if match:
                    plan_days = int(float(match.get("days", 0) or 0))
            except Exception:
                plan_days = 0

            sheets.mark_manual_renewal_reminded(sub_id, plan_days=plan_days)
            results["manual_renewal_alerts"] += 1

    except Exception as e:
        results["errors"].append(f"manual_renewals: {e}")

    return results
