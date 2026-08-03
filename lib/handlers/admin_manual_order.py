"""
Admin: Manual Order Creation
Admin can create a subscription for any user directly — no payment required.
Also handles 42-day manual renewal acknowledgement.
"""
import telebot
from telebot import types
from datetime import datetime, timedelta

from lib import sheets, config
from lib.messages import MANUAL_ORDER_CREATED, ERROR_GENERIC
from lib.bot_helpers import admin_main_keyboard


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


# ─── Conversation state per admin session ─────────────────────────────────────
# key: admin_chat_id, value: dict of collected fields
_state: dict = {}


def register(bot: telebot.TeleBot):

    # ── Entry point ──────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_manual_order")
    def cb_manual_order(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)
        _state[call.message.chat.id] = {}
        bot.send_message(
            call.message.chat.id,
            "📋 *Manual Order — Step 1/5*\n\n"
            "Enter the *Telegram User ID* of the customer\n"
            "_(They must have started the bot at least once)_",
            parse_mode="Markdown",
            reply_markup=_cancel_markup(),
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id, lambda m: _step_user_id(bot, m)
        )

    @bot.message_handler(commands=["manual_order"])
    def cmd_manual_order(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        _state[message.chat.id] = {}
        bot.send_message(
            message.chat.id,
            "📋 *Manual Order — Step 1/5*\n\n"
            "Enter the *Telegram User ID* of the customer:",
            parse_mode="Markdown",
            reply_markup=_cancel_markup(),
        )
        bot.register_next_step_handler_by_chat_id(
            message.chat.id, lambda m: _step_user_id(bot, m)
        )

    # ── Step 1: User ID ───────────────────────────────────────────────────────

    def _step_user_id(bot, message):
        if message.text == "❌ Cancel":
            _cancel(bot, message)
            return
        try:
            user_id = int(message.text.strip())
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid ID. Enter a numeric Telegram user ID:")
            bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _step_user_id(bot, m))
            return

        user = sheets.get_user(user_id)
        _state[message.chat.id]["user_id"] = user_id
        _state[message.chat.id]["username"] = user.get("username", "") if user else ""
        _state[message.chat.id]["chat_id"] = int(user.get("chat_id") or user_id) if user else user_id
        _state[message.chat.id]["first_name"] = user.get("first_name", "") if user else ""

        display = f"@{user['username']}" if user and user.get("username") else f"ID:{user_id}"
        bot.send_message(
            message.chat.id,
            f"✅ User: *{display}*\n\n"
            f"📋 *Step 2/5* — Select *Product Type*:",
            parse_mode="Markdown",
            reply_markup=_product_markup(),
        )
        bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _step_product(bot, m))

    # ── Step 2: Product ───────────────────────────────────────────────────────

    def _step_product(bot, message):
        if message.text == "❌ Cancel":
            _cancel(bot, message)
            return
        product = message.text.strip().upper()
        if product not in ("ZOOM", "CANVA"):
            bot.send_message(message.chat.id, "❌ Choose: ZOOM or CANVA", reply_markup=_product_markup())
            bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _step_product(bot, m))
            return

        _state[message.chat.id]["product_type"] = product
        bot.send_message(
            message.chat.id,
            f"✅ Product: *{product}*\n\n"
            f"📋 *Step 3/5* — Enter *Plan Name*\n_(e.g. Zoom 1 Month, Canva 1 Year)_",
            parse_mode="Markdown",
            reply_markup=_cancel_markup(),
        )
        bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _step_plan(bot, m))

    # ── Step 3: Plan name ─────────────────────────────────────────────────────

    def _step_plan(bot, message):
        if message.text == "❌ Cancel":
            _cancel(bot, message)
            return
        _state[message.chat.id]["plan_name"] = message.text.strip()
        bot.send_message(
            message.chat.id,
            f"✅ Plan: *{message.text.strip()}*\n\n"
            f"📋 *Step 4/5* — How many *days* is this subscription valid?\n_(e.g. 30, 365)_",
            parse_mode="Markdown",
            reply_markup=_cancel_markup(),
        )
        bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _step_days(bot, m))

    # ── Step 4: Days ──────────────────────────────────────────────────────────

    def _step_days(bot, message):
        if message.text == "❌ Cancel":
            _cancel(bot, message)
            return
        try:
            days = int(message.text.strip())
            if days <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(message.chat.id, "❌ Enter a valid number of days (e.g. 30):")
            bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _step_days(bot, m))
            return

        _state[message.chat.id]["days"] = days
        bot.send_message(
            message.chat.id,
            f"✅ Duration: *{days} days*\n\n"
            f"📋 *Step 5/5* — Enter *delivery info* to send to customer\n"
            f"_(Account credentials, invite link, etc. Type `-` to skip)_",
            parse_mode="Markdown",
            reply_markup=_cancel_markup(),
        )
        bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _step_delivery(bot, m))

    # ── Step 5: Delivery info + confirm ───────────────────────────────────────

    def _step_delivery(bot, message):
        if message.text == "❌ Cancel":
            _cancel(bot, message)
            return
        delivery = "" if message.text.strip() == "-" else message.text.strip()
        _state[message.chat.id]["key_or_link"] = delivery

        s = _state[message.chat.id]
        expiry = (datetime.utcnow() + timedelta(days=s["days"])).strftime("%Y-%m-%d")

        # Show confirmation with 42-day option
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add("✅ Confirm (Normal)")
        markup.add("🔁 Confirm + Track 42-day Renewals")
        markup.add("❌ Cancel")

        bot.send_message(
            message.chat.id,
            f"📋 *Confirm Manual Order*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"User:    @{s.get('username') or s['user_id']}\n"
            f"Product: {s['product_type']}\n"
            f"Plan:    {s['plan_name']}\n"
            f"Days:    {s['days']}\n"
            f"Expiry:  {expiry}\n"
            f"Delivery: {'(none)' if not delivery else delivery[:40]}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"Choose *Confirm + Track 42-day Renewals* if you need to manually "
            f"renew this account every 42 days and want reminders.",
            parse_mode="Markdown",
            reply_markup=markup,
        )
        bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _step_confirm(bot, m))

    # ── Confirm ───────────────────────────────────────────────────────────────

    def _step_confirm(bot, message):
        if message.text == "❌ Cancel":
            _cancel(bot, message)
            return

        needs_renewal = "42" in message.text
        s = _state.get(message.chat.id, {})
        if not s:
            bot.send_message(message.chat.id, "❌ Session expired. Start again with /manual_order")
            return

        try:
            sub = sheets.create_manual_subscription(
                user_id=s["user_id"],
                chat_id=s["chat_id"],
                username=s.get("username", ""),
                product_type=s["product_type"],
                plan_name=s["plan_name"],
                days=s["days"],
                key_or_link=s.get("key_or_link", ""),
                needs_manual_renewal=needs_renewal,
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error creating subscription: {e}",
                             reply_markup=types.ReplyKeyboardRemove())
            return

        expiry = sub.get("expiry_date", "")[:10]
        renewal_note = "\n🔁 *42-day renewal reminders enabled.*" if needs_renewal else ""

        # Notify admin
        bot.send_message(
            message.chat.id,
            f"✅ Manual subscription created!\n"
            f"Sub ID: `{sub['id']}`\nExpiry: {expiry}{renewal_note}",
            parse_mode="Markdown",
            reply_markup=types.ReplyKeyboardRemove(),
        )

        # Notify the customer
        try:
            delivery_text = s.get("key_or_link", "")
            customer_msg = MANUAL_ORDER_CREATED.format(
                order_id=sub["id"],
                product=s["product_type"],
                plan_name=s["plan_name"],
                expiry=expiry,
            )
            if delivery_text:
                customer_msg += f"\n\n📦 *Your Access Details:*\n`{delivery_text}`"
            bot.send_message(s["chat_id"], customer_msg, parse_mode="Markdown")

            # Send thermal receipt
            try:
                import io as _io
                from lib.receipt import generate_receipt
                start_str = sub.get("created_at", datetime.utcnow().strftime("%Y-%m-%d"))
                if hasattr(start_str, "strftime"):
                    start_str = start_str.strftime("%Y-%m-%d")
                start_str = str(start_str)[:10]
                receipt_png = generate_receipt(
                    order_id=sub["id"],
                    product=s["product_type"],
                    plan_name=s["plan_name"],
                    start_date=start_str,
                    expiry_date=expiry,
                    username=s.get("username", ""),
                )
                bot.send_photo(
                    s["chat_id"],
                    _io.BytesIO(receipt_png),
                    caption="🧾 *Your Official Receipt*\nKhant Digital Products • @KhantsManagerBot",
                    parse_mode="Markdown",
                )
            except Exception as _re:
                print(f"Receipt error: {_re}")

        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Could not notify customer: {e}")


        # Cleanup state
        _state.pop(message.chat.id, None)

    # ── 42-day renewal acknowledgement ────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_renewed_"))
    def cb_mark_renewed(call: types.CallbackQuery):
        """Admin taps 'Mark as Renewed' after doing the provider-side renewal."""
        if not is_admin(call.from_user.id):
            return
        sub_id = call.data.replace("admin_renewed_", "")
        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            f"📅 Enter new expiry date for `{sub_id}`\nFormat: `YYYY-MM-DD`",
            parse_mode="Markdown",
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            lambda m: _update_renewal_expiry(bot, m, sub_id)
        )

    def _update_renewal_expiry(bot, message, sub_id):
        try:
            new_expiry = message.text.strip()
            datetime.strptime(new_expiry, "%Y-%m-%d")  # validate format
            sheets.update_manual_renewal_expiry(sub_id, new_expiry + " 00:00:00")
            sheets.mark_manual_renewal_reminded(sub_id)
            bot.send_message(
                message.chat.id,
                f"✅ `{sub_id}` expiry updated to `{new_expiry}`.\n"
                f"Next reminder scheduled in 42 days.",
                parse_mode="Markdown",
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid date format. Use YYYY-MM-DD")
            bot.register_next_step_handler_by_chat_id(
                message.chat.id,
                lambda m: _update_renewal_expiry(bot, m, sub_id)
            )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _cancel_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("❌ Cancel")
    return markup


def _product_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("ZOOM", "CANVA")
    markup.add("❌ Cancel")
    return markup


def _cancel(bot, message):
    _state.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id,
        "❌ Manual order cancelled.",
        reply_markup=types.ReplyKeyboardRemove(),
    )
