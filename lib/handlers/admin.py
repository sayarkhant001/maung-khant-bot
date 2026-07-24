"""
Admin panel: payment approval, user management, broadcast, reports, coupons, plans.
All handlers require ADMIN_ID check.
"""
import telebot
from telebot import types

from lib import sheets, config
from lib.messages import ADMIN_PANEL, ERROR_GENERIC
from lib.bot_helpers import admin_main_keyboard


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


def register(bot: telebot.TeleBot):

    @bot.message_handler(commands=["admin"])
    def cmd_admin(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        bot.send_message(
            message.chat.id,
            ADMIN_PANEL,
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
    def cb_admin_panel(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            ADMIN_PANEL,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard(),
        )

    # ── Reports ──────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_reports")
    def cb_reports(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id, "Loading stats...")
        try:
            s = sheets.get_stats()
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)
            return

        text = f"""📊 *Bot Statistics*
━━━━━━━━━━━━━━━━━━━
👥 Total Users:        {s['total_users']}
📦 Active Subs:        {s['active_subscriptions']}
━━━━━━━━━━━━━━━━━━━
🧾 Total Orders:       {s['total_orders']}
✅ Approved:           {s['approved_orders']}
⏳ Pending Review:     {s['pending_orders']}
━━━━━━━━━━━━━━━━━━━
💰 Total Revenue:      {s['total_revenue']:,} MMK
📅 Today's Orders:     {s['today_orders']}
📅 Today's Revenue:    {s['today_revenue']:,} MMK"""

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel"))

        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup,
        )

    # ── Pending Orders ────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_pending")
    def cb_pending(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)
        try:
            orders = sheets.get_pending_orders()
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)
            return

        if not orders:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel"))
            bot.edit_message_text(
                "✅ No pending orders.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup,
            )
            return

        # Show all pending orders
        markup = types.InlineKeyboardMarkup(row_width=1)
        for o in orders[:20]:
            markup.add(types.InlineKeyboardButton(
                f"🧾 {o['order_id']} · @{o.get('username','?')} · {o['product_type']} · {o['amount']} MMK",
                callback_data=f"admin_order_{o['order_id']}"
            ))
        markup.add(types.InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel"))

        bot.edit_message_text(
            f"⏳ *Pending Orders* ({len(orders)})",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup,
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_order_"))
    def cb_view_order(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        order_id = call.data.replace("admin_order_", "")
        bot.answer_callback_query(call.id)

        order = sheets.get_order(order_id)
        if not order:
            bot.answer_callback_query(call.id, "Order not found.", show_alert=True)
            return

        text = f"""🧾 *Order Details*
━━━━━━━━━━━━━━━━━━━
Order ID:  `{order['order_id']}`
User:      @{order.get('username','N/A')} (`{order['user_id']}`)
Product:   {order['product_type']}
Plan:      {order['plan_name']}
Amount:    {order['amount']} MMK
Method:    {order.get('payment_method','N/A')}
Status:    {order['status']}
Created:   {order.get('created_at','')}"""

        from lib.bot_helpers import admin_order_keyboard
        markup = admin_order_keyboard(order_id)
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_pending"))

        # Send screenshot if available
        file_id = order.get("screenshot_file_id", "")
        if file_id:
            bot.send_photo(
                call.message.chat.id,
                file_id,
                caption=text,
                parse_mode="Markdown",
                reply_markup=markup,
            )
        else:
            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="Markdown",
                reply_markup=markup,
            )

    # ── Approve / Decline ─────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_approve_"))
    def cb_approve(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        order_id = call.data.replace("admin_approve_", "")
        bot.answer_callback_query(call.id)

        order = sheets.approve_order(order_id)
        if not order:
            bot.answer_callback_query(call.id, "Order not found.", show_alert=True)
            return

        # Ask admin for delivery details (key/link/credentials)
        msg = bot.send_message(
            call.message.chat.id,
            f"✅ Order `{order_id}` approved.\n\n"
            f"📤 Send the delivery info to forward to the user:\n"
            f"_(VPN key, Zoom credentials, Canva invite link, etc.)_",
            parse_mode="Markdown",
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            lambda m: _deliver_product(bot, m, order)
        )

    def _deliver_product(bot: telebot.TeleBot, message: types.Message, order: dict):
        delivery_info = message.text or ""
        user_chat_id = int(order.get("chat_id") or order.get("user_id"))
        product_type = order.get("product_type", "")

        # Create subscription
        plan_days = 30  # Default; ideally looked up from plan
        sub = sheets.create_subscription(
            user_id=int(order["user_id"]),
            chat_id=user_chat_id,
            product_type=product_type,
            plan_name=order.get("plan_name", ""),
            days=plan_days,
            key_or_link=delivery_info[:500],
            order_id=order["order_id"],
        )

        from lib.messages import ORDER_VERIFIED_MANUAL
        user_msg = ORDER_VERIFIED_MANUAL.format(
            order_id=order["order_id"],
            product=f"{product_type} — {order.get('plan_name','')}",
            delivery_info=delivery_info,
        )

        try:
            bot.send_message(user_chat_id, user_msg, parse_mode="Markdown")
            bot.send_message(
                message.chat.id,
                f"✅ Delivery sent to user.\nSubscription created: `{sub['id']}`",
                parse_mode="Markdown",
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Failed to notify user: {e}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_decline_"))
    def cb_decline(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        order_id = call.data.replace("admin_decline_", "")
        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            f"❌ Declining order `{order_id}`.\nSend a reason (optional):",
            parse_mode="Markdown",
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            lambda m: _do_decline(bot, m, order_id)
        )

    def _do_decline(bot: telebot.TeleBot, message: types.Message, order_id: str):
        reason = message.text or "Payment could not be verified."
        order = sheets.get_order(order_id)
        sheets.decline_order(order_id, admin_note=reason)

        if order:
            user_chat_id = int(order.get("chat_id") or order.get("user_id"))
            from lib.messages import ORDER_DECLINED
            try:
                bot.send_message(
                    user_chat_id,
                    ORDER_DECLINED.format(
                        order_id=order_id,
                        support=config.SUPPORT_USERNAME,
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        bot.send_message(message.chat.id, f"✅ Order `{order_id}` declined.", parse_mode="Markdown")

    # ── Users ─────────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data in ("admin_users",) or
                                c.data.startswith("admin_users_page_"))
    def cb_users(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id, "Loading users...")
        page = 0
        if call.data.startswith("admin_users_page_"):
            page = int(call.data.replace("admin_users_page_", ""))

        users = sheets.get_all_users()
        from lib.bot_helpers import admin_users_keyboard
        bot.edit_message_text(
            f"👥 *Users* ({len(users)} total)",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=admin_users_keyboard(users, page),
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_user_") and
                                not c.data.startswith("admin_user_orders_"))
    def cb_user_detail(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        user_id = int(call.data.replace("admin_user_", ""))
        bot.answer_callback_query(call.id)

        user = sheets.get_user(user_id)
        if not user:
            bot.answer_callback_query(call.id, "User not found.", show_alert=True)
            return

        subs = sheets.get_user_subscriptions(user_id)
        orders = sheets.get_user_orders(user_id)
        is_blocked = str(user.get("is_blocked", "")).upper() == "TRUE"

        text = f"""👤 *User Details*
━━━━━━━━━━━━━━━━━━━
Name:       {user.get('first_name','')} @{user.get('username','N/A')}
ID:         `{user_id}`
Joined:     {user.get('joined_at','')[:10]}
Blocked:    {'Yes ⛔' if is_blocked else 'No ✅'}
Active Subs: {len(subs)}
Orders:     {len(orders)}"""

        from lib.bot_helpers import admin_user_detail_keyboard
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=admin_user_detail_keyboard(user_id, is_blocked),
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_toggle_block_"))
    def cb_toggle_block(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        user_id = int(call.data.replace("admin_toggle_block_", ""))
        user = sheets.get_user(user_id)
        if not user:
            return
        is_blocked = str(user.get("is_blocked", "")).upper() == "TRUE"
        sheets.set_user_blocked(user_id, not is_blocked)
        action = "Unblocked" if is_blocked else "Blocked"
        bot.answer_callback_query(call.id, f"{action} user {user_id}.")

    # ── Broadcast ─────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_broadcast")
    def cb_broadcast(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📢 *Broadcast*\n\nSend the message to broadcast to all users:",
            parse_mode="Markdown",
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            lambda m: _do_broadcast(bot, m)
        )

    def _do_broadcast(bot: telebot.TeleBot, message: types.Message):
        text = message.text or ""
        if not text:
            bot.send_message(message.chat.id, "❌ Empty message. Broadcast cancelled.")
            return

        users = sheets.get_all_users()
        success = 0
        fail = 0
        for u in users:
            if str(u.get("is_blocked", "")).upper() == "TRUE":
                continue
            try:
                chat_id = int(u.get("chat_id") or u.get("user_id"))
                bot.send_message(chat_id, text, parse_mode="Markdown")
                success += 1
            except Exception:
                fail += 1

        bot.send_message(
            message.chat.id,
            f"📢 Broadcast complete.\n✅ Sent: {success}\n❌ Failed: {fail}",
        )

    # ── Coupons ───────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_coupons")
    def cb_coupons(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)
        coupons = sheets.get_all_coupons()
        from lib.bot_helpers import admin_coupons_keyboard
        bot.edit_message_text(
            f"🎟️ *Coupons* ({len(coupons)} total)",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=admin_coupons_keyboard(coupons),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_coupon_new")
    def cb_new_coupon(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🎟️ *New Coupon*\n\n"
            "Send coupon details in this format:\n"
            "`CODE PRODUCT PLAN_NAME DAYS MAX_USES`\n\n"
            "Example:\n`GIFT2024 VPN 30GB-30Day 30 5`",
            parse_mode="Markdown",
        )
        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            lambda m: _create_coupon(bot, m)
        )

    def _create_coupon(bot: telebot.TeleBot, message: types.Message):
        try:
            parts = message.text.strip().split()
            if len(parts) < 5:
                raise ValueError("Not enough parts")
            code, product, plan, days, max_uses = parts[0], parts[1], parts[2], int(parts[3]), int(parts[4])
            coupon = sheets.create_coupon(code, product.upper(), plan, days, max_uses)
            bot.send_message(
                message.chat.id,
                f"✅ Coupon created!\nCode: `{code}`\nProduct: {product}\nPlan: {plan}\nDays: {days}\nMax Uses: {max_uses}",
                parse_mode="Markdown",
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Error: {e}\n\nFormat: `CODE PRODUCT PLAN_NAME DAYS MAX_USES`",
                parse_mode="Markdown",
            )

    # ── 42-Day Manual Renewals List ───────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_renewals")
    def cb_renewals(call: types.CallbackQuery):
        if not is_admin(call.from_user.id):
            return
        bot.answer_callback_query(call.id, "Loading renewals...")
        try:
            records = sheets._sheet_to_dicts(sheets.get_sheet("manual_renewals"))
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)
            return

        active = [r for r in records if str(r.get("is_active", "")).upper() == "TRUE"]

        if not active:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel"))
            bot.edit_message_text(
                "✅ No active manual renewal subscriptions.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup,
            )
            return

        from datetime import datetime
        now = datetime.utcnow()
        text = f"🔁 *Manual Renewal Subscriptions* ({len(active)} active)\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)

        for r in active:
            sub_id = r.get("sub_id", "")
            username = r.get("username", "N/A")
            product = r.get("product_type", "")
            plan = r.get("plan_name", "")
            expiry_str = str(r.get("expiry_date", ""))[:10]
            next_remind = str(r.get("next_remind_at", ""))[:10]

            # Days until expiry
            try:
                exp_dt = datetime.strptime(expiry_str, "%Y-%m-%d")
                days_left = (exp_dt - now).days
                days_label = f"{days_left}d left" if days_left >= 0 else "EXPIRED"
            except Exception:
                days_label = "?"

            # Days until next reminder
            try:
                nxt_dt = datetime.strptime(next_remind, "%Y-%m-%d")
                remind_in = (nxt_dt - now).days
                remind_label = f"remind in {remind_in}d" if remind_in >= 0 else "DUE NOW"
            except Exception:
                remind_label = "?"

            text += (
                f"👤 @{username} · {product} · {plan}\n"
                f"   Expiry: `{expiry_str}` ({days_label}) | {remind_label}\n"
                f"   Sub: `{sub_id}`\n\n"
            )
            markup.add(types.InlineKeyboardButton(
                f"✅ Mark Renewed: {sub_id}",
                callback_data=f"admin_renewed_{sub_id}"
            ))

        markup.add(types.InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel"))

        # May exceed edit limit; send new message
        bot.send_message(
            call.message.chat.id,
            text,
            parse_mode="Markdown",
            reply_markup=markup,
        )

