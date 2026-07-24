"""
Gift / Coupon redemption handler.
"""
import telebot
from telebot import types
from datetime import datetime

from lib import sheets, config
from lib.messages import (
    ERROR_INVALID_COUPON, ERROR_COUPON_CLAIMED,
    SUCCESS_COUPON_CLAIMED, ERROR_GENERIC
)
from lib.bot_helpers import back_to_main


def register(bot: telebot.TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "menu_coupon")
    def cb_coupon_menu(call: types.CallbackQuery):
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home"))

        msg = bot.edit_message_text(
            "🎟️ *Redeem Coupon*\n\nSend your coupon code:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup,
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            lambda m: _process_coupon(bot, m)
        )

    def _process_coupon(bot: telebot.TeleBot, message: types.Message):
        code = message.text.strip().upper() if message.text else ""
        user_id = message.from_user.id

        if not code:
            bot.send_message(
                message.chat.id,
                "❌ Please send a valid coupon code.",
                reply_markup=back_to_main(),
            )
            return

        coupon = sheets.get_coupon(code)

        if not coupon or str(coupon.get("is_active", "")).upper() != "TRUE":
            bot.send_message(
                message.chat.id, ERROR_INVALID_COUPON,
                parse_mode="Markdown",
                reply_markup=back_to_main(),
            )
            return

        # Check expiry
        exp_str = coupon.get("expires_at", "")
        if exp_str:
            try:
                exp = datetime.strptime(str(exp_str), "%Y-%m-%d %H:%M:%S")
                if datetime.utcnow() > exp:
                    bot.send_message(
                        message.chat.id, ERROR_INVALID_COUPON,
                        parse_mode="Markdown",
                        reply_markup=back_to_main(),
                    )
                    return
            except Exception:
                pass

        # Check if user already used this coupon
        if sheets.has_used_coupon(code, user_id):
            bot.send_message(
                message.chat.id, ERROR_COUPON_CLAIMED,
                parse_mode="Markdown",
                reply_markup=back_to_main(),
            )
            return

        # Check uses limit
        max_uses = int(coupon.get("max_uses", 1) or 1)
        used = int(coupon.get("used_count", 0) or 0)
        if used >= max_uses:
            bot.send_message(
                message.chat.id, ERROR_INVALID_COUPON,
                parse_mode="Markdown",
                reply_markup=back_to_main(),
            )
            return

        # Activate subscription
        product_type = coupon.get("product_type", "").upper()
        plan_name = coupon.get("plan_name", "")
        days = int(coupon.get("days", 30) or 30)

        sheets.upsert_user(
            user_id=user_id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            chat_id=message.chat.id,
        )

        sub = sheets.create_subscription(
            user_id=user_id,
            chat_id=message.chat.id,
            product_type=product_type,
            plan_name=plan_name,
            days=days,
        )

        # Mark coupon as used
        sheets.use_coupon(code, user_id, sub["id"])

        expiry_date = sub.get("expiry_date", "")
        if isinstance(expiry_date, str) and len(expiry_date) > 10:
            expiry_date = expiry_date[:10]

        bot.send_message(
            message.chat.id,
            SUCCESS_COUPON_CLAIMED.format(
                product=product_type,
                plan_name=plan_name,
                expiry_date=expiry_date,
            ),
            parse_mode="Markdown",
            reply_markup=back_to_main(),
        )

        # Notify admin of coupon use
        try:
            bot.send_message(
                config.ADMIN_ID,
                f"🎟️ Coupon `{code}` used by @{message.from_user.username or user_id}\n"
                f"Product: {product_type} · {plan_name} · {days} days",
                parse_mode="Markdown",
            )
        except Exception:
            pass
