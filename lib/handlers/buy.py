"""
Buy flow: Zoom Pro & Canva Pro only (VPN removed — will be added later).
Category → Plan → [Email if required] → Checkout → Payment method → Screenshot → Admin notified.
"""
import re
import telebot
from telebot import types

from lib import sheets, config
from lib.messages import (
    BUY_MENU, ZOOM_CATEGORY_TEXT, CANVA_CATEGORY_TEXT,
    PAYMENT_INSTRUCTIONS, ORDER_PENDING_MANUAL, ORDER_NOTIFICATION,
    EMAIL_REQUEST, EMAIL_INVALID,
)
from lib.bot_helpers import (
    buy_menu_keyboard, zoom_plans_keyboard, canva_plans_keyboard,
    payment_methods_keyboard, back_to_buy, format_payment_methods,
    admin_order_keyboard
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(text: str) -> bool:
    return bool(_EMAIL_RE.match(text.strip()))


def register(bot: telebot.TeleBot):

    # ── Browse menu ───────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "menu_buy")
    def cb_buy(call: types.CallbackQuery):
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            BUY_MENU,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=buy_menu_keyboard(),
        )

    # ── Zoom ─────────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "cat_zoom")
    def cb_cat_zoom(call: types.CallbackQuery):
        bot.answer_callback_query(call.id)
        plans = sheets.get_active_zoom_plans()
        if not plans:
            bot.answer_callback_query(call.id, "No Zoom plans available right now.", show_alert=True)
            return
        renew_eligible = sheets.is_renewal_eligible(call.from_user.id, "ZOOM")
        bot.edit_message_text(
            ZOOM_CATEGORY_TEXT,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=zoom_plans_keyboard(plans, renew_eligible=renew_eligible),
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan_zoom_"))
    def cb_plan_zoom(call: types.CallbackQuery):
        plan_id = call.data.replace("plan_zoom_", "")
        _handle_plan_selection(bot, call, "zoom_plans", "ZOOM", plan_id)

    # ── Canva ─────────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "cat_canva")
    def cb_cat_canva(call: types.CallbackQuery):
        bot.answer_callback_query(call.id)
        plans = sheets.get_active_canva_plans()
        if not plans:
            bot.answer_callback_query(call.id, "No Canva plans available right now.", show_alert=True)
            return
        renew_eligible = sheets.is_renewal_eligible(call.from_user.id, "CANVA")
        bot.edit_message_text(
            CANVA_CATEGORY_TEXT,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=canva_plans_keyboard(plans, renew_eligible=renew_eligible),
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan_canva_"))
    def cb_plan_canva(call: types.CallbackQuery):
        plan_id = call.data.replace("plan_canva_", "")
        _handle_plan_selection(bot, call, "canva_plans", "CANVA", plan_id)

    # ── Payment method selection ──────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_method_"))
    def cb_pay_method(call: types.CallbackQuery):
        # Format: pay_method_{order_id}_{method_name}
        raw = call.data.replace("pay_method_", "")
        if "_" not in raw:
            bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
            return
        idx = raw.index("_", 4)  # skip past "ORD-"
        order_id = raw[:idx]
        method_name = raw[idx + 1:]

        sheets.update_order(order_id, payment_method=method_name)
        bot.answer_callback_query(call.id)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="menu_home"))

        bot.edit_message_text(
            f"✅ Method selected: *{method_name}*\n\n"
            f"📸 Now send your *payment screenshot* as the next message.\n\n"
            f"Order ID: `{order_id}`",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup,
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            lambda msg: _receive_screenshot(bot, msg, order_id)
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _handle_plan_selection(bot, call, sheet_name, product_type, plan_id):
    """
    Route plan selection: if plan requires_email → ask for email first,
    otherwise go straight to checkout.
    """
    bot.answer_callback_query(call.id)
    plan = sheets.get_plan(sheet_name, plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "Plan not found.", show_alert=True)
        return

    requires_email = str(plan.get("requires_email", "")).upper() == "TRUE"

    if requires_email:
        # Ask customer for their email before checkout
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="menu_buy"))
        msg = bot.send_message(
            call.message.chat.id,
            EMAIL_REQUEST.format(plan_name=plan["name"]),
            parse_mode="Markdown",
            reply_markup=markup,
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            lambda m: _collect_email(bot, m, sheet_name, product_type, plan_id, attempt=1),
        )
    else:
        _show_checkout(bot, call.message.chat.id, sheet_name, product_type, plan_id,
                       user=call.from_user, customer_email="")


def _collect_email(bot, message, sheet_name, product_type, plan_id, attempt=1):
    """Validate the email the customer typed, then proceed to checkout."""
    text = (message.text or "").strip()

    if not _is_valid_email(text):
        if attempt >= 3:
            bot.send_message(
                message.chat.id,
                "❌ Too many invalid attempts. Please restart with /start.",
            )
            return
        bot.send_message(message.chat.id, EMAIL_INVALID, parse_mode="Markdown")
        bot.register_next_step_handler_by_chat_id(
            message.chat.id,
            lambda m: _collect_email(bot, m, sheet_name, product_type, plan_id, attempt + 1),
        )
        return

    customer_email = text
    _show_checkout(bot, message.chat.id, sheet_name, product_type, plan_id,
                   user=message.from_user, customer_email=customer_email)


def _show_checkout(bot, chat_id, sheet_name, product_type, plan_id, user, customer_email=""):
    """Create order and display payment instructions."""
    plan = sheets.get_plan(sheet_name, plan_id)
    if not plan:
        bot.send_message(chat_id, "❌ Plan not found. Please try again.")
        return

    sheets.upsert_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        chat_id=chat_id,
    )

    # Determine price: renewal eligible users get renew_price if set
    renew_eligible = sheets.is_renewal_eligible(user.id, product_type)
    rp = str(plan.get("renew_price", "")).strip()
    if renew_eligible and rp and rp not in ("", "0", "0.0"):
        chosen_price = int(float(rp))
        price_label  = f"{rp} MMK (Renewal Price)"
    else:
        chosen_price = int(float(plan["price"]))
        price_label  = f"{plan['price']} MMK"

    order = sheets.create_order(
        user_id=user.id,
        chat_id=chat_id,
        username=user.username or "",
        product_type=product_type,
        plan_name=plan["name"],
        amount=chosen_price,
        customer_email=customer_email,
    )

    methods = sheets.get_active_payment_methods()
    methods_text = format_payment_methods(methods) if methods else "_No payment methods configured yet._"

    # Build optional email line for payment summary
    email_line = f"📧  Email     `{customer_email}`\n" if customer_email else ""

    text = PAYMENT_INSTRUCTIONS.format(
        plan_name=plan["name"],
        amount=price_label,
        email_line=email_line,
        payment_methods=methods_text,
    )
    text += f"\n\nOrder ID: `{order['order_id']}`"

    bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=payment_methods_keyboard(methods, order["order_id"]) if methods else back_to_buy(),
    )


def _receive_screenshot(bot, message, order_id):
    if not message.photo:
        bot.send_message(
            message.chat.id,
            "❌ Please send a *photo* (screenshot) of your payment receipt.",
            parse_mode="Markdown",
        )
        bot.register_next_step_handler_by_chat_id(
            message.chat.id,
            lambda msg: _receive_screenshot(bot, msg, order_id)
        )
        return

    file_id = message.photo[-1].file_id
    order = sheets.get_order(order_id)
    if not order:
        bot.send_message(message.chat.id, "❌ Order not found. Please start again.")
        return

    sheets.attach_screenshot(order_id, file_id, order.get("payment_method", ""))

    bot.send_message(
        message.chat.id,
        ORDER_PENDING_MANUAL.format(order_id=order_id),
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")
        ),
    )

    # Notify admin — include email if present
    try:
        customer_email = order.get("customer_email", "")
        email_line = f"\nEmail    `{customer_email}`" if customer_email else ""
        caption = ORDER_NOTIFICATION.format(
            order_id=order["order_id"],
            username=message.from_user.username or "N/A",
            user_id=message.from_user.id,
            product=order["product_type"],
            plan_name=order["plan_name"],
            amount=order["amount"],
            method=order.get("payment_method", "Unknown"),
            email_line=email_line,
        )
        bot.send_photo(
            config.ADMIN_ID,
            file_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=admin_order_keyboard(order["order_id"]),
        )
    except Exception:
        pass
