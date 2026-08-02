"""
Keyboard builders and helper utilities for the bot.
"""
from telebot import types
from typing import List, Dict


# ─── Main Menus ───────────────────────────────────────────────────────────────

def main_menu_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 Buy Plans", callback_data="menu_buy"),
        types.InlineKeyboardButton("📦 My Subscriptions", callback_data="menu_my_subs"),
    )
    markup.add(
        types.InlineKeyboardButton("🎟️ Redeem Coupon", callback_data="menu_coupon"),
        types.InlineKeyboardButton("💬 Support", callback_data="menu_support"),
    )
    return markup


def buy_menu_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎥 Zoom Pro Plans", callback_data="cat_zoom"),
        types.InlineKeyboardButton("🎨 Canva Pro Plans", callback_data="cat_canva"),
    )
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home"))
    return markup


def back_to_main() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home"))
    return markup


def back_to_buy() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("⬅️ Back to Plans", callback_data="menu_buy"),
        types.InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home"),
    )
    return markup


# ─── Plan Keyboards ───────────────────────────────────────────────────────────

def zoom_plans_keyboard(plans: List[Dict]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p in sorted(plans, key=lambda x: int(x.get("sort_order", 99) or 99)):
        label = f"🎥 {p['name']} · {p['days']} days · {p['price']} MMK"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"plan_zoom_{p['id']}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu_buy"))
    return markup


def canva_plans_keyboard(plans: List[Dict]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p in sorted(plans, key=lambda x: int(x.get("sort_order", 99) or 99)):
        label = f"🎨 {p['name']} · {p['days']} days · {p['price']} MMK"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"plan_canva_{p['id']}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="menu_buy"))
    return markup


# ─── Payment Keyboards ────────────────────────────────────────────────────────

def payment_methods_keyboard(methods: List[Dict], order_id: str) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    for m in methods:
        label = f"{m.get('icon', '💳')} {m['name']} · {m['account_info']}"
        markup.add(types.InlineKeyboardButton(
            label, callback_data=f"pay_method_{order_id}_{m['name']}"
        ))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="menu_home"))
    return markup


def admin_order_keyboard(order_id: str) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{order_id}"),
        types.InlineKeyboardButton("❌ Decline", callback_data=f"admin_decline_{order_id}"),
    )
    return markup


def admin_approve_delivery_keyboard(order_id: str, product_type: str) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(
        "📤 Send Delivery Info", callback_data=f"admin_deliver_{order_id}"
    ))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_pending"))
    return markup


# ─── Admin Panel Keyboards ────────────────────────────────────────────────────

def admin_main_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("🧾 Orders",       callback_data="admin_pending"),
        types.InlineKeyboardButton("📦 Plans",        callback_data="admin_plans"),
    )
    markup.row(
        types.InlineKeyboardButton("📋 Manual Order", callback_data="admin_manual_order"),
        types.InlineKeyboardButton("🔁 42d Renewals", callback_data="admin_renewals"),
    )
    markup.row(
        types.InlineKeyboardButton("💳 Payments",    callback_data="admin_payments"),
        types.InlineKeyboardButton("👥 Users",        callback_data="admin_users"),
    )
    markup.row(
        types.InlineKeyboardButton("📢 Broadcast",   callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🎟️ Coupons",     callback_data="admin_coupons"),
    )
    markup.row(
        types.InlineKeyboardButton("📈 Reports",     callback_data="admin_reports"),
        types.InlineKeyboardButton("📊 Stats",       callback_data="admin_stats"),
    )
    return markup


def admin_users_keyboard(users: List[Dict], page: int = 0) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    per_page = 10
    start = page * per_page
    page_users = users[start:start + per_page]
    for u in page_users:
        name = u.get("first_name") or u.get("username") or str(u.get("user_id"))
        markup.add(types.InlineKeyboardButton(
            f"👤 {name}", callback_data=f"admin_user_{u['user_id']}"
        ))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"admin_users_page_{page-1}"))
    if start + per_page < len(users):
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"admin_users_page_{page+1}"))
    if nav:
        markup.add(*nav)
    markup.add(types.InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel"))
    return markup


def admin_user_detail_keyboard(user_id: int, is_blocked: bool) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    block_label = "🔓 Unblock" if is_blocked else "🚫 Block"
    markup.add(
        types.InlineKeyboardButton(block_label, callback_data=f"admin_toggle_block_{user_id}"),
        types.InlineKeyboardButton("📋 Orders", callback_data=f"admin_user_orders_{user_id}"),
    )
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_users"))
    return markup


def admin_coupons_keyboard(coupons: List[Dict]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    for c in coupons[:15]:
        status = "✅" if str(c.get("is_active", "")).upper() == "TRUE" else "❌"
        used = c.get("used_count", 0)
        max_u = c.get("max_uses", 1)
        markup.add(types.InlineKeyboardButton(
            f"{status} {c['code']} · {c['product_type']} · {used}/{max_u} uses",
            callback_data=f"admin_coupon_{c['code']}"
        ))
    markup.add(
        types.InlineKeyboardButton("➕ New Coupon", callback_data="admin_coupon_new"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"),
    )
    return markup


# ─── Subscription Display ─────────────────────────────────────────────────────

def format_subscription(sub: Dict) -> str:
    product = sub.get("product_type", "Unknown")
    plan = sub.get("plan_name", "")
    expiry = sub.get("expiry_date", "N/A")
    if isinstance(expiry, str) and len(expiry) > 10:
        expiry = expiry[:10]

    icons = {"VPN": "🔐", "ZOOM": "🎥", "CANVA": "🎨"}
    icon = icons.get(product.upper(), "📦")

    text = f"{icon} *{product} — {plan}*\n"
    text += f"📅 Expires: `{expiry}`\n"

    if sub.get("key_or_link"):
        text += f"🔑 Key: `{sub['key_or_link']}`\n"

    data_limit = sub.get("data_limit_gb")
    if data_limit and str(data_limit) not in ("", "0"):
        used = sub.get("data_used_gb", 0) or 0
        text += f"💾 Data: {used}/{data_limit} GB\n"

    return text


def format_payment_methods(methods: List[Dict]) -> str:
    lines = []
    for m in methods:
        icon = m.get("icon", "💳")
        acc = m.get('account_info', '')
        name = m.get('account_name', '')
        note = m.get('note', '')
        
        block = f"{icon} *{m.get('name', 'Bank')}*\n"
        if name:
            block += f"👤 {name}\n"
        block += f"🔢 `{acc}`\n"
        if note:
            block += f"📝 _{note}_\n"
            
        lines.append(block.strip())
    return "\n\n".join(lines)
