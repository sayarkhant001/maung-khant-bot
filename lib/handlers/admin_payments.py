"""
Admin: Payment Methods Management
- List all methods with account info
- Add new method (wizard)
- Edit method (name, account number, account name, note)
- Toggle active/inactive
- Delete method
"""
import telebot
from telebot import types
from lib import sheets, config

_state: dict = {}


def is_admin(uid): return uid == config.ADMIN_ID


def register(bot: telebot.TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "admin_payments")
    def cb_payments(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id)
        _show_methods(bot, call.message.chat.id, call.message.message_id)

    def _show_methods(bot, chat_id, edit_id=None):
        methods = sheets._sheet_to_dicts(sheets.get_sheet("payment_methods"))
        markup = types.InlineKeyboardMarkup(row_width=2)
        text = "💳 *Payment Methods*\n\n"

        for m in methods:
            icon = m.get("icon", "💳")
            status = "✅" if str(m.get("status","")).lower() == "active" else "❌"
            text += (f"{status} {icon} *{m.get('method_name','')}*\n"
                     f"   Account: `{m.get('account_info','')}`\n\n")
            markup.row(
                types.InlineKeyboardButton(f"✏️ Edit",   callback_data=f"pm_edit_{m['id']}"),
                types.InlineKeyboardButton(f"🗑️ Delete", callback_data=f"pm_del_{m['id']}"),
            )

        markup.add(types.InlineKeyboardButton("➕ Add Method", callback_data="pm_add"))
        markup.add(types.InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel"))

        if edit_id:
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=edit_id,
                    parse_mode="Markdown", reply_markup=markup)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

    # ── Add Method ────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "pm_add")
    def cb_pm_add(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id)
        _state[call.message.chat.id] = {"action": "add_pm", "step": 1, "data": {}}
        bot.send_message(call.message.chat.id,
            "💳 *Add Payment Method*\n\n*Step 1/4* — Method name (e.g. KBZPay):",
            parse_mode="Markdown", reply_markup=_cancel_kb())
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, lambda m: _pm_step(bot, m))

    def _pm_step(bot, message):
        if message.text == "❌ Cancel":
            _state.pop(message.chat.id, None)
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=types.ReplyKeyboardRemove())
            return
        s = _state.get(message.chat.id, {})
        step = s.get("step", 1)
        prompts = {
            1: ("method_name",   "*Step 2/4* — Account number:", 2),
            2: ("account_info",  "*Step 3/4* — Account holder name:", 3),
            3: ("account_name",  "*Step 4/4* — Note to show users (e.g. 'Don\\'t write VPN in note'):", 4),
        }
        if step in prompts:
            field, next_prompt, next_step = prompts[step]
            s["data"][field] = message.text.strip()
            s["step"] = next_step
            _state[message.chat.id] = s
            bot.send_message(message.chat.id, next_prompt,
                parse_mode="Markdown", reply_markup=_cancel_kb())
            bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _pm_step(bot, m))
        elif step == 4:
            s["data"]["note"] = message.text.strip()
            data = s["data"]
            _state.pop(message.chat.id, None)
            try:
                ws = sheets.get_sheet("payment_methods")
                headers = sheets.SHEET_SCHEMAS["payment_methods"]
                existing = sheets._sheet_to_dicts(ws)
                new_id = str(max([int(p.get("id",0) or 0) for p in existing] + [0]) + 1)
                row = {h: "" for h in headers}
                row.update({"id": new_id, "method_name": data["method_name"],
                             "method_type": "Mobile Wallet",
                             "account_info": data["account_info"],
                             "icon": "💳", "status": "active"})
                ws.append_row([row[h] for h in headers])
                bot.send_message(message.chat.id,
                    f"✅ *{data['method_name']}* added!\nAccount: `{data['account_info']}`",
                    parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error: {e}",
                    reply_markup=types.ReplyKeyboardRemove())

    # ── Edit Method ───────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pm_edit_"))
    def cb_pm_edit(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        method_id = call.data.replace("pm_edit_", "")
        bot.answer_callback_query(call.id)
        methods = sheets._sheet_to_dicts(sheets.get_sheet("payment_methods"))
        m = next((x for x in methods if str(x.get("id")) == method_id), None)
        if not m:
            bot.send_message(call.message.chat.id, "❌ Not found."); return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("✏️ Method Name",   callback_data=f"pm_field_{method_id}_method_name"),
            types.InlineKeyboardButton("💳 Account No.",   callback_data=f"pm_field_{method_id}_account_info"),
            types.InlineKeyboardButton("👤 Account Name",  callback_data=f"pm_field_{method_id}_account_name"),
            types.InlineKeyboardButton("🔄 Toggle Status", callback_data=f"pm_toggle_{method_id}"),
            types.InlineKeyboardButton("⬅️ Back",          callback_data="admin_payments"),
        )
        status = "✅ Active" if str(m.get("status","")).lower() == "active" else "❌ Inactive"
        bot.send_message(call.message.chat.id,
            f"✏️ *Edit {m.get('method_name','')}*\n\n"
            f"Account: `{m.get('account_info','')}`\n"
            f"Status: {status}",
            parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pm_toggle_"))
    def cb_pm_toggle(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        method_id = call.data.replace("pm_toggle_", "")
        bot.answer_callback_query(call.id)
        ws = sheets.get_sheet("payment_methods")
        headers = sheets.SHEET_SCHEMAS["payment_methods"]
        methods = sheets._sheet_to_dicts(ws)
        m = next((x for x in methods if str(x.get("id")) == method_id), None)
        if not m: return
        new_status = "inactive" if str(m.get("status","")).lower() == "active" else "active"
        row_idx = sheets._find_row(ws, "id", method_id, headers)
        col = headers.index("status") + 1
        ws.update_cell(row_idx, col, new_status)
        bot.send_message(call.message.chat.id,
            f"✅ {m.get('method_name','')} → *{new_status}*", parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pm_field_"))
    def cb_pm_field(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        # pm_field_{method_id}_{field_name}
        raw = call.data.replace("pm_field_", "")
        idx = raw.rfind("_")
        method_id = raw[:idx]; field = raw[idx+1:]
        bot.answer_callback_query(call.id)
        _state[call.message.chat.id] = {"action": "edit_pm", "method_id": method_id, "field": field}
        labels = {"method_name": "new method name", "account_info": "new account number",
                  "account_name": "new account holder name"}
        bot.send_message(call.message.chat.id,
            f"Enter the {labels.get(field, field)}:",
            reply_markup=_cancel_kb())
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, lambda m: _save_pm_field(bot, m))

    def _save_pm_field(bot, message):
        if message.text == "❌ Cancel":
            _state.pop(message.chat.id, None)
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=types.ReplyKeyboardRemove())
            return
        s = _state.pop(message.chat.id, {})
        method_id = s.get("method_id"); field = s.get("field")
        try:
            ws = sheets.get_sheet("payment_methods")
            headers = sheets.SHEET_SCHEMAS["payment_methods"]
            row_idx = sheets._find_row(ws, "id", method_id, headers)
            col = headers.index(field) + 1
            ws.update_cell(row_idx, col, message.text.strip())
            bot.send_message(message.chat.id,
                f"✅ *{field}* updated.", parse_mode="Markdown",
                reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {e}",
                reply_markup=types.ReplyKeyboardRemove())

    # ── Delete Method ─────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pm_del_"))
    def cb_pm_del(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        method_id = call.data.replace("pm_del_", "")
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Yes", callback_data=f"pm_del_confirm_{method_id}"),
            types.InlineKeyboardButton("❌ No",  callback_data="admin_payments"),
        )
        bot.send_message(call.message.chat.id,
            f"⚠️ Delete payment method `{method_id}`?",
            parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pm_del_confirm_"))
    def cb_pm_del_confirm(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        method_id = call.data.replace("pm_del_confirm_", "")
        bot.answer_callback_query(call.id)
        try:
            ws = sheets.get_sheet("payment_methods")
            headers = sheets.SHEET_SCHEMAS["payment_methods"]
            row_idx = sheets._find_row(ws, "id", method_id, headers)
            if row_idx:
                ws.delete_rows(row_idx)
                bot.send_message(call.message.chat.id, "✅ Method deleted.")
            else:
                bot.send_message(call.message.chat.id, "❌ Not found.")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {e}")
        _show_methods(bot, call.message.chat.id)


def _cancel_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("❌ Cancel")
    return kb
