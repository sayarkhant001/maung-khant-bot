"""
User-facing handlers: /start, main menu, my subscriptions, support.
"""
import telebot
from telebot import types

from lib import sheets, config
from lib.messages import (
    WELCOME_MESSAGE, MAIN_MENU_TEXT, MY_SUBSCRIPTIONS_HEADER,
    NO_SUBSCRIPTIONS, SUPPORT_MESSAGE, ERROR_GENERIC
)
from lib.bot_helpers import main_menu_keyboard, back_to_main, format_subscription


def register(bot: telebot.TeleBot):

    @bot.message_handler(commands=["start"])
    def cmd_start(message: types.Message):
        user = message.from_user
        try:
            sheets.upsert_user(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                chat_id=message.chat.id,
            )
            db_user = sheets.get_user(user.id)
            if db_user and str(db_user.get("is_blocked", "")).upper() == "TRUE":
                bot.send_message(message.chat.id, "🚫 Your account has been suspended. Contact support.")
                return
        except Exception as e:
            pass  # Non-critical — still show welcome

        bot.send_message(
            message.chat.id,
            WELCOME_MESSAGE,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "menu_home")
    def cb_home(call: types.CallbackQuery):
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            MAIN_MENU_TEXT,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "menu_my_subs")
    def cb_my_subs(call: types.CallbackQuery):
        bot.answer_callback_query(call.id)
        try:
            subs = sheets.get_user_subscriptions(call.from_user.id)
        except Exception:
            bot.answer_callback_query(call.id, "Error loading subscriptions.", show_alert=True)
            return

        if not subs:
            bot.edit_message_text(
                NO_SUBSCRIPTIONS,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=back_to_main(),
            )
            return

        text = MY_SUBSCRIPTIONS_HEADER + "\n\n"
        for sub in subs:
            text += format_subscription(sub) + "\n"
            text += "─────────────────\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Renew", callback_data="menu_buy"),
            types.InlineKeyboardButton("🏠 Menu", callback_data="menu_home"),
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup,
        )

    @bot.callback_query_handler(func=lambda c: c.data == "menu_support")
    def cb_support(call: types.CallbackQuery):
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            SUPPORT_MESSAGE.format(support_username=config.SUPPORT_USERNAME),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=back_to_main(),
        )
