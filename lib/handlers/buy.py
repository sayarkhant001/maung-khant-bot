"""
Buy flow: Zoom Pro & Canva Pro only (VPN removed — will be added later).
Category → Plan → Checkout → Payment method → Screenshot → Admin notified.
"""
import telebot
from telebot import types

from lib import sheets, config
from lib.messages import (
    BUY_MENU, ZOOM_CATEGORY_TEXT, CANVA_CATEGORY_TEXT,
    PAYMENT_INSTRUCTIONS, ORDER_PENDING_MANUAL, ORDER_NOTIFICATION
)
from lib.bot_helpers import (
    buy_menu_keyboard, zoom_plans_keyboard, canva_plans_keyboard,
    payment_methods_keyboard, back_to_buy, format_payment_methods,
    admin_order_keyboard
)


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
        _show_checkout(bot, call, "zoom_plans", "ZOOM", plan_id)

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
        _show_checkout(bot, call, "canva_plans", "CANVA", plan_id)

    # ── Payment method selection ──────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_method_"))
    def cb_pay_method(call: types.CallbackQuery):
        # Format: pay_method_{order_id}_{method_name}
        raw = call.data.replace("pay_method_", "")
        # order_id is always "ORD-XXXXXXXX" (12 chars fixed), rest is method
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

def _show_checkout(bot, call, sheet_name, product_type, plan_id):
    bot.answer_callback_query(call.id)
    plan = sheets.get_plan(sheet_name, plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "Plan not found.", show_alert=True)
        return

    user = call.from_user
    sheets.upsert_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        chat_id=call.message.chat.id,
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
        chat_id=call.message.chat.id,
        username=user.username or "",
        product_type=product_type,
        plan_name=plan["name"],
        amount=chosen_price,
    )

    methods = sheets.get_active_payment_methods()
    methods_text = format_payment_methods(methods) if methods else "_No payment methods configured yet._"

    text = PAYMENT_INSTRUCTIONS.format(
        plan_name=plan["name"],
        amount=price_label,
        payment_methods=methods_text,
    )
    text += f"\n\nOrder ID: `{order['order_id']}`"

    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
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

    # Notify admin
    try:
        caption = ORDER_NOTIFICATION.format(
            order_id=order["order_id"],
            username=message.from_user.username or "N/A",
            user_id=message.from_user.id,
            product=order["product_type"],
            plan_name=order["plan_name"],
            amount=order["amount"],
            method=order.get("payment_method", "Unknown"),
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
