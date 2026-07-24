"""
Admin: Plans Management (Zoom & Canva)
- View all plans
- Add a new plan (wizard)
- Edit plan price/days/status
- Delete plan
"""
import telebot
from telebot import types

from lib import sheets, config

# Per-admin wizard state
_state: dict = {}


def is_admin(uid): return uid == config.ADMIN_ID


def register(bot: telebot.TeleBot):

    # ── Entry: Plans Menu ────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_plans")
    def cb_plans_menu(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎥 Zoom Plans",  callback_data="plans_zoom"),
            types.InlineKeyboardButton("🎨 Canva Plans", callback_data="plans_canva"),
        )
        markup.add(types.InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel"))
        bot.edit_message_text("📦 *Plan Management*\n\nSelect a product:",
            chat_id=call.message.chat.id, message_id=call.message.message_id,
            parse_mode="Markdown", reply_markup=markup)

    # ── List Plans ───────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data in ("plans_zoom", "plans_canva"))
    def cb_list_plans(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id)
        product = "zoom" if call.data == "plans_zoom" else "canva"
        _show_plans(bot, call.message.chat.id, product, call.message.message_id)

    def _show_plans(bot, chat_id, product, edit_id=None):
        sheet_name = f"{product}_plans"
        plans = sheets._sheet_to_dicts(sheets.get_sheet(sheet_name))
        emoji = "🎥" if product == "zoom" else "🎨"
        label = "Zoom" if product == "zoom" else "Canva"

        markup = types.InlineKeyboardMarkup(row_width=2)
        text = f"{emoji} *{label} Plans* ({len(plans)} total)\n\n"

        for p in sorted(plans, key=lambda x: int(x.get("sort_order") or 99)):
            status_icon = "✅" if str(p.get("status","")).lower() == "active" else "❌"
            text += (f"{status_icon} *{p.get('name','')}*\n"
                     f"   {p.get('days','')}d · {int(float(p.get('price',0))):,} MMK\n")
            markup.row(
                types.InlineKeyboardButton(f"✏️ Edit", callback_data=f"plan_edit_{product}_{p['id']}"),
                types.InlineKeyboardButton(f"🗑️ Del",  callback_data=f"plan_del_{product}_{p['id']}"),
            )

        markup.add(types.InlineKeyboardButton(f"➕ Add Plan", callback_data=f"plan_add_{product}"))
        markup.add(types.InlineKeyboardButton("⬅️ Plans Menu", callback_data="admin_plans"))

        if edit_id:
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=edit_id,
                    parse_mode="Markdown", reply_markup=markup)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

    # ── Delete Plan ───────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan_del_"))
    def cb_del_plan(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        _, _, product, plan_id = call.data.split("_", 3)
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Yes, Delete", callback_data=f"plan_del_confirm_{product}_{plan_id}"),
            types.InlineKeyboardButton("❌ Cancel",      callback_data=f"plans_{product}"),
        )
        bot.send_message(call.message.chat.id,
            f"⚠️ Delete plan `{plan_id}` from *{product}*?\nThis cannot be undone.",
            parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan_del_confirm_"))
    def cb_del_confirm(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        parts = call.data.replace("plan_del_confirm_", "").split("_", 1)
        product, plan_id = parts[0], parts[1]
        bot.answer_callback_query(call.id)
        try:
            ws = sheets.get_sheet(f"{product}_plans")
            headers = sheets.SHEET_SCHEMAS[f"{product}_plans"]
            row_idx = sheets._find_row(ws, "id", plan_id, headers)
            if row_idx:
                ws.delete_rows(row_idx)
                bot.send_message(call.message.chat.id, f"✅ Plan `{plan_id}` deleted.")
            else:
                bot.send_message(call.message.chat.id, "❌ Plan not found.")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {e}")
        _show_plans(bot, call.message.chat.id, product)

    # ── Edit Plan ─────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan_edit_"))
    def cb_edit_plan(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        parts = call.data.replace("plan_edit_", "").split("_", 1)
        product, plan_id = parts[0], parts[1]
        bot.answer_callback_query(call.id)

        ws = sheets.get_sheet(f"{product}_plans")
        headers = sheets.SHEET_SCHEMAS[f"{product}_plans"]
        plans = sheets._sheet_to_dicts(ws)
        plan = next((p for p in plans if str(p.get("id")) == str(plan_id)), None)
        if not plan:
            bot.send_message(call.message.chat.id, "❌ Plan not found.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("✏️ Change Name",   callback_data=f"plan_field_{product}_{plan_id}_name"),
            types.InlineKeyboardButton("💰 Change Price",  callback_data=f"plan_field_{product}_{plan_id}_price"),
            types.InlineKeyboardButton("📅 Change Days",   callback_data=f"plan_field_{product}_{plan_id}_days"),
            types.InlineKeyboardButton("🔄 Toggle Status", callback_data=f"plan_toggle_{product}_{plan_id}"),
            types.InlineKeyboardButton("⬅️ Back",          callback_data=f"plans_{product}"),
        )
        bot.send_message(
            call.message.chat.id,
            f"✏️ *Edit Plan*\n\n"
            f"Name:   {plan.get('name')}\n"
            f"Days:   {plan.get('days')}\n"
            f"Price:  {int(float(plan.get('price',0))):,} MMK\n"
            f"Status: {plan.get('status')}",
            parse_mode="Markdown", reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan_toggle_"))
    def cb_toggle_status(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        parts = call.data.replace("plan_toggle_", "").split("_", 1)
        product, plan_id = parts[0], parts[1]
        bot.answer_callback_query(call.id)
        ws = sheets.get_sheet(f"{product}_plans")
        headers = sheets.SHEET_SCHEMAS[f"{product}_plans"]
        plans = sheets._sheet_to_dicts(ws)
        plan = next((p for p in plans if str(p.get("id")) == str(plan_id)), None)
        if not plan:
            bot.send_message(call.message.chat.id, "❌ Not found."); return
        new_status = "inactive" if plan.get("status") == "active" else "active"
        row_idx = sheets._find_row(ws, "id", plan_id, headers)
        col = headers.index("status") + 1
        ws.update_cell(row_idx, col, new_status)
        bot.send_message(call.message.chat.id, f"✅ Plan status → *{new_status}*", parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan_field_"))
    def cb_plan_field(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        # plan_field_{product}_{plan_id}_{field}
        raw = call.data.replace("plan_field_", "")
        parts = raw.split("_")
        product, plan_id, field = parts[0], parts[1], parts[2]
        bot.answer_callback_query(call.id)
        _state[call.message.chat.id] = {"action": "edit_plan", "product": product,
                                          "plan_id": plan_id, "field": field}
        labels = {"name": "new name", "price": "new price (numbers only, MMK)", "days": "number of days"}
        bot.send_message(call.message.chat.id,
            f"Enter the {labels.get(field, field)} for this plan:",
            reply_markup=_cancel_kb())
        bot.register_next_step_handler_by_chat_id(call.message.chat.id,
            lambda m: _save_plan_field(bot, m))

    def _save_plan_field(bot, message):
        if message.text == "❌ Cancel":
            _state.pop(message.chat.id, None)
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=types.ReplyKeyboardRemove())
            return
        s = _state.pop(message.chat.id, {})
        product = s.get("product"); plan_id = s.get("plan_id"); field = s.get("field")
        value = message.text.strip()
        try:
            ws = sheets.get_sheet(f"{product}_plans")
            headers = sheets.SHEET_SCHEMAS[f"{product}_plans"]
            row_idx = sheets._find_row(ws, "id", plan_id, headers)
            col = headers.index(field) + 1
            ws.update_cell(row_idx, col, value)
            bot.send_message(message.chat.id, f"✅ *{field}* updated to `{value}`",
                parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {e}",
                reply_markup=types.ReplyKeyboardRemove())

    # ── Add Plan ──────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan_add_"))
    def cb_add_plan(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        product = call.data.replace("plan_add_", "")
        bot.answer_callback_query(call.id)
        _state[call.message.chat.id] = {"action": "add_plan", "product": product, "step": 1, "data": {}}
        bot.send_message(call.message.chat.id,
            f"➕ *Add {product.title()} Plan*\n\n*Step 1/4* — Enter plan name:",
            parse_mode="Markdown", reply_markup=_cancel_kb())
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, lambda m: _add_plan_step(bot, m))

    def _add_plan_step(bot, message):
        if message.text == "❌ Cancel":
            _state.pop(message.chat.id, None)
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=types.ReplyKeyboardRemove())
            return
        s = _state.get(message.chat.id, {})
        step = s.get("step", 1)
        prompts = {1: ("name", "*Step 2/4* — Enter selling price (MMK):", 2),
                   2: ("price", "*Step 3/4* — Enter buying price (MMK):", 3),
                   3: ("buying_price", "*Step 4/4* — Enter number of days:", 4)}
        if step in prompts:
            field, next_prompt, next_step = prompts[step]
            s["data"][field] = message.text.strip()
            s["step"] = next_step
            _state[message.chat.id] = s
            bot.send_message(message.chat.id, next_prompt,
                parse_mode="Markdown", reply_markup=_cancel_kb())
            bot.register_next_step_handler_by_chat_id(message.chat.id, lambda m: _add_plan_step(bot, m))
        elif step == 4:
            s["data"]["days"] = message.text.strip()
            product = s["product"]
            data = s["data"]
            _state.pop(message.chat.id, None)
            try:
                ws = sheets.get_sheet(f"{product}_plans")
                headers = sheets.SHEET_SCHEMAS[f"{product}_plans"]
                existing = sheets._sheet_to_dicts(ws)
                new_id = str(max([int(p.get("id",0) or 0) for p in existing] + [0]) + 1)
                sort_order = str(len(existing) + 1)
                row = {h: "" for h in headers}
                row.update({"id": new_id, "name": data["name"], "days": data["days"],
                             "price": data["price"], "buying_price": data["buying_price"],
                             "status": "active", "sort_order": sort_order})
                ws.append_row([row[h] for h in headers])
                bot.send_message(message.chat.id,
                    f"✅ *{data['name']}* added!\nID: `{new_id}` · {data['days']}d · {data['price']} MMK",
                    parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error: {e}",
                    reply_markup=types.ReplyKeyboardRemove())


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cancel_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("❌ Cancel")
    return kb
