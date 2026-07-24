"""
Admin Reports: Dashboard, Active Subs Summary, Daily/Weekly, CSV Export
Matches production: active subs by type, revenue, CSV download.
"""
import io
import csv
import telebot
from telebot import types
from datetime import datetime, timedelta
from lib import sheets, config


def is_admin(uid): return uid == config.ADMIN_ID


def register(bot: telebot.TeleBot):

    @bot.callback_query_handler(func=lambda c: c.data == "admin_reports")
    def cb_reports_menu(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📊 Active Subscriptions",  callback_data="report_active_subs"),
            types.InlineKeyboardButton("📅 Daily Summary",         callback_data="report_daily"),
            types.InlineKeyboardButton("📅 Weekly Summary",        callback_data="report_weekly"),
            types.InlineKeyboardButton("📄 Export CSV (Active)",   callback_data="report_export_active"),
            types.InlineKeyboardButton("📄 Export CSV (All)",      callback_data="report_export_all"),
            types.InlineKeyboardButton("⬅️ Admin Panel",           callback_data="admin_panel"),
        )
        bot.send_message(call.message.chat.id,
            "📈 *Reports Dashboard*\n\nSelect a report:",
            parse_mode="Markdown", reply_markup=markup)

    # ── Active Subscriptions Report ───────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "report_active_subs")
    def cb_active_subs(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id, "Generating...")

        subs = sheets._sheet_to_dicts(sheets.get_sheet("subscriptions"))
        now = datetime.utcnow() + timedelta(seconds=getattr(sheets, '_clock_offset_seconds', 0))

        active = []
        for s in subs:
            if str(s.get("status","")).lower() != "active":
                continue
            try:
                exp = datetime.strptime(str(s["expiry_date"])[:19], "%Y-%m-%d %H:%M:%S")
                if exp > now:
                    active.append(s)
            except Exception:
                pass

        by_type = {}
        for s in active:
            pt = str(s.get("product_type","UNKNOWN")).upper()
            by_type[pt] = by_type.get(pt, 0) + 1

        expired_count = sum(1 for s in subs if str(s.get("status","")).lower() == "expired")
        total_users = len(sheets._sheet_to_dicts(sheets.get_sheet("users")))

        text = (f"📊 *Active Subscriptions Report*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👥 Total Users:    {total_users}\n"
                f"✅ Active Subs:    {len(active)}\n"
                f"❌ Expired Subs:   {expired_count}\n"
                f"━━━━━━━━━━━━━━━━━━━\n")
        for pt, cnt in sorted(by_type.items()):
            emoji = {"ZOOM": "🎥", "CANVA": "🎨", "VPN": "🔐"}.get(pt, "📦")
            text += f"{emoji} {pt:10}: {cnt}\n"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📄 Export CSV (Active)", callback_data="report_export_active"),
            types.InlineKeyboardButton("📄 Export CSV (All)",    callback_data="report_export_all"),
            types.InlineKeyboardButton("⬅️ Back",               callback_data="admin_reports"),
        )
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

    # ── Daily Summary ─────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "report_daily")
    def cb_daily(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id, "Calculating...")
        _send_period_report(bot, call.message.chat.id, days=1, label="Daily")

    @bot.callback_query_handler(func=lambda c: c.data == "report_weekly")
    def cb_weekly(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        bot.answer_callback_query(call.id, "Calculating...")
        _send_period_report(bot, call.message.chat.id, days=7, label="Weekly")

    def _send_period_report(bot, chat_id, days, label):
        orders = sheets._sheet_to_dicts(sheets.get_sheet("orders"))
        offset = timedelta(seconds=getattr(sheets, '_clock_offset_seconds', 0))
        now = datetime.utcnow() + offset
        cutoff = now - timedelta(days=days)

        period_orders = []
        for o in orders:
            if str(o.get("status","")).lower() not in ("approved", "manual", "verified"):
                continue
            try:
                created = datetime.strptime(str(o.get("created_at",""))[:19], "%Y-%m-%d %H:%M:%S")
                if created >= cutoff:
                    period_orders.append(o)
            except Exception:
                pass

        total_revenue = sum(int(float(o.get("amount", 0) or 0)) for o in period_orders)
        by_product = {}
        for o in period_orders:
            pt = str(o.get("product_type","?")).upper()
            by_product[pt] = by_product.get(pt, 0) + 1

        text = (f"📅 *{label} Report* ({now.strftime('%Y-%m-%d')})\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🧾 Orders:     {len(period_orders)}\n"
                f"💰 Revenue:    {total_revenue:,} MMK\n"
                f"━━━━━━━━━━━━━━━━━━━\n")
        for pt, cnt in sorted(by_product.items()):
            text += f"  {pt}: {cnt} orders\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Reports", callback_data="admin_reports"))
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

    # ── CSV Export ────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data in ("report_export_active", "report_export_all"))
    def cb_export_csv(call: types.CallbackQuery):
        if not is_admin(call.from_user.id): return
        include_expired = call.data == "report_export_all"
        bot.answer_callback_query(call.id, "Generating CSV...")

        subs = sheets._sheet_to_dicts(sheets.get_sheet("subscriptions"))
        users = {str(u.get("user_id")): u
                 for u in sheets._sheet_to_dicts(sheets.get_sheet("users"))}

        offset = timedelta(seconds=getattr(sheets, '_clock_offset_seconds', 0))
        now = datetime.utcnow() + offset

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Username", "User ID", "Product", "Plan", "Email/Key",
                         "Status", "Start Date", "Expiry Date", "Days Left"])

        for s in sorted(subs, key=lambda x: x.get("expiry_date",""), reverse=True):
            status = str(s.get("status","")).lower()
            if not include_expired and status != "active":
                continue

            user_id = str(s.get("user_id",""))
            u = users.get(user_id, {})
            username = f"@{u.get('username','')}" if u.get("username") else user_id

            try:
                exp = datetime.strptime(str(s.get("expiry_date",""))[:19], "%Y-%m-%d %H:%M:%S")
                days_left = (exp - now).days
                days_label = f"{days_left}d" if days_left >= 0 else "EXPIRED"
            except Exception:
                exp = None; days_label = "?"

            writer.writerow([
                s.get("id",""), username, user_id,
                s.get("product_type",""), s.get("plan_name",""),
                s.get("key_or_link","") or s.get("email",""),
                status.upper(),
                str(s.get("created_at",""))[:10],
                str(s.get("expiry_date",""))[:10],
                days_label,
            ])

        output.seek(0)
        file_bytes = io.BytesIO(output.getvalue().encode("utf-8-sig"))  # utf-8-sig = Excel-safe
        label = "all" if include_expired else "active"
        file_bytes.name = f"{label}_subscriptions_{now.strftime('%Y%m%d')}.csv"

        bot.send_document(
            call.message.chat.id, file_bytes,
            caption=f"📄 {'All' if include_expired else 'Active'} subscriptions export — {now.strftime('%Y-%m-%d')}",
        )
