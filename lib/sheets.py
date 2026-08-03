"""
Google Sheets Database Adapter
Replaces SQLAlchemy + SQLite with Google Sheets as the data store.

Sheet names and their column schemas are defined in SHEET_SCHEMAS.
All operations use gspread with a cached service account client.
"""

import base64
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

import requests
import gspread
from google.oauth2.service_account import Credentials
import google.auth._helpers as _ga_helpers

from lib.config import GOOGLE_SERVICE_ACCOUNT_JSON_BASE64, GOOGLE_SPREADSHEET_ID

# ─── Clock Skew Fix ───────────────────────────────────────────────────────────
# Windows machines without proper NTP sometimes have clock drift that breaks
# Google JWT auth ("invalid_grant: Token must be short-lived").
# This patch fetches real UTC from Telegram's server header and corrects it.

_clock_offset_seconds: float = 0.0


def _sync_clock():
    """Fetch real UTC from Telegram response header and compute offset."""
    global _clock_offset_seconds
    try:
        r = requests.head(
            "https://api.telegram.org",
            timeout=5,
        )
        server_date = r.headers.get("Date", "")
        if server_date:
            from email.utils import parsedate_to_datetime
            server_utc = parsedate_to_datetime(server_date).replace(tzinfo=None)
            local_utc = datetime.utcnow()
            _clock_offset_seconds = (server_utc - local_utc).total_seconds()
    except Exception:
        _clock_offset_seconds = 0.0


def _corrected_utcnow() -> datetime:
    """Return real UTC time corrected for system clock skew."""
    return datetime.utcnow() + timedelta(seconds=_clock_offset_seconds)


# Patch google-auth to use corrected time for JWT signing
_ga_helpers.utcnow = _corrected_utcnow  # type: ignore

# Sync once at import time
_sync_clock()


# ─── Sheet Column Definitions ─────────────────────────────────────────────────

SHEET_SCHEMAS = {
    "users": [
        "user_id", "username", "first_name", "chat_id",
        "joined_at", "last_active", "is_blocked", "total_orders"
    ],
    "orders": [
        "order_id", "user_id", "chat_id", "username", "product_type",
        "plan_name", "amount", "status", "payment_method",
        "screenshot_file_id", "created_at", "expires_at",
        "admin_note", "verified_at", "subscription_id"
    ],
    "subscriptions": [
        "id", "user_id", "chat_id", "username", "product_type", "plan_name",
        "expiry_date", "status", "key_or_link", "email",
        "data_limit_gb", "data_used_gb", "reminder_3day_sent",
        "reminder_1day_sent", "reminder_0day_sent", "created_at"
    ],
    "coupons": [
        "code", "product_type", "plan_name", "days", "discount_pct",
        "max_uses", "used_count", "is_active", "created_at", "expires_at"
    ],
    "coupon_uses": [
        "id", "code", "user_id", "used_at", "subscription_id"
    ],
    "vpn_plans": [
        "id", "name", "vpn_type", "days", "data_limit_gb",
        "price", "renew_price", "buying_price", "status", "sort_order"
    ],
    "zoom_plans": [
        "id", "name", "days", "price", "renew_price", "buying_price", "status", "sort_order"
    ],
    "canva_plans": [
        "id", "name", "days", "price", "renew_price", "buying_price", "status", "sort_order"
    ],
    "payment_methods": [
        "id", "name", "type", "account_info", "account_name", "note", "icon", "is_active"
    ],
    "rate_limits": [
        "user_id", "last_request_at"
    ],
    "broadcast_log": [
        "id", "message", "sent_at", "sent_by", "success_count", "fail_count"
    ],
    "system_config": [
        "key", "value", "updated_at"
    ],
    # Tracks subscriptions that need admin manual renewal every 42 days
    "manual_renewals": [
        "sub_id", "user_id", "username", "product_type", "plan_name",
        "expiry_date", "last_reminded_at", "next_remind_at", "is_active"
    ],
}

# ─── Client Setup ─────────────────────────────────────────────────────────────

_client: Optional[gspread.Client] = None
_spreadsheet: Optional[gspread.Spreadsheet] = None
_sheet_cache: Dict[str, gspread.Worksheet] = {}


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        json_bytes = base64.b64decode(GOOGLE_SERVICE_ACCOUNT_JSON_BASE64)
        service_account_info = json.loads(json_bytes.decode("utf-8"))
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        _client = gspread.authorize(creds)
    return _client


def _get_spreadsheet() -> gspread.Spreadsheet:
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = _get_client().open_by_key(GOOGLE_SPREADSHEET_ID)
    return _spreadsheet


def get_sheet(name: str) -> gspread.Worksheet:
    """Get or cache a worksheet by name."""
    if name not in _sheet_cache:
        ss = _get_spreadsheet()
        try:
            ws = ss.worksheet(name)
        except gspread.WorksheetNotFound:
            # Create it with headers
            ws = ss.add_worksheet(title=name, rows=1000, cols=len(SHEET_SCHEMAS.get(name, [])) + 1)
            headers = SHEET_SCHEMAS.get(name, [])
            if headers:
                ws.append_row(headers)
        _sheet_cache[name] = ws
    return _sheet_cache[name]


# ─── Low-Level Helpers ────────────────────────────────────────────────────────

def _sheet_to_dicts(ws: gspread.Worksheet) -> List[Dict[str, Any]]:
    """Return all rows as list of dicts."""
    records = ws.get_all_records(default_blank="")
    return records


def _find_row(ws: gspread.Worksheet, col_name: str, value: Any, headers: List[str]) -> Optional[int]:
    """Return 1-based row index (including header row) or None."""
    col_idx = headers.index(col_name) + 1  # 1-based
    col_values = ws.col_values(col_idx)
    str_val = str(value)
    for i, v in enumerate(col_values):
        if i == 0:  # skip header
            continue
        if str(v) == str_val:
            return i + 1  # 1-based row number
    return None


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _gen_id(prefix: str = "") -> str:
    return prefix + str(uuid.uuid4())[:8].upper()


# ─── Users ────────────────────────────────────────────────────────────────────

def get_user(user_id: int) -> Optional[Dict]:
    ws = get_sheet("users")
    records = _sheet_to_dicts(ws)
    for r in records:
        if str(r.get("user_id")) == str(user_id):
            return r
    return None


def upsert_user(user_id: int, username: str, first_name: str, chat_id: int) -> Dict:
    ws = get_sheet("users")
    headers = SHEET_SCHEMAS["users"]
    existing = get_user(user_id)
    if existing:
        # Update last_active and username
        row_idx = _find_row(ws, "user_id", user_id, headers)
        if row_idx:
            la_col = headers.index("last_active") + 1
            un_col = headers.index("username") + 1
            fn_col = headers.index("first_name") + 1
            ws.update_cell(row_idx, la_col, _now())
            ws.update_cell(row_idx, un_col, username or "")
            ws.update_cell(row_idx, fn_col, first_name or "")
        return existing
    else:
        row = {h: "" for h in headers}
        row.update({
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "chat_id": chat_id,
            "joined_at": _now(),
            "last_active": _now(),
            "is_blocked": "FALSE",
            "total_orders": 0,
        })
        ws.append_row([row[h] for h in headers])
        return row


def get_all_users() -> List[Dict]:
    return _sheet_to_dicts(get_sheet("users"))


def set_user_blocked(user_id: int, blocked: bool):
    ws = get_sheet("users")
    headers = SHEET_SCHEMAS["users"]
    row_idx = _find_row(ws, "user_id", user_id, headers)
    if row_idx:
        col = headers.index("is_blocked") + 1
        ws.update_cell(row_idx, col, "TRUE" if blocked else "FALSE")


# ─── Plans ────────────────────────────────────────────────────────────────────

def get_active_vpn_plans() -> List[Dict]:
    plans = _sheet_to_dicts(get_sheet("vpn_plans"))
    return [p for p in plans if str(p.get("status", "")).lower() == "active"]


def get_active_zoom_plans() -> List[Dict]:
    plans = _sheet_to_dicts(get_sheet("zoom_plans"))
    return [p for p in plans if str(p.get("status", "")).lower() == "active"]


def get_active_canva_plans() -> List[Dict]:
    plans = _sheet_to_dicts(get_sheet("canva_plans"))
    return [p for p in plans if str(p.get("status", "")).lower() == "active"]


def get_plan(sheet_name: str, plan_id: str) -> Optional[Dict]:
    records = _sheet_to_dicts(get_sheet(sheet_name))
    for r in records:
        if str(r.get("id")) == str(plan_id):
            return r
    return None


def get_active_payment_methods() -> List[Dict]:
    methods = _sheet_to_dicts(get_sheet("payment_methods"))
    return [m for m in methods if str(m.get("is_active", "")).upper() == "TRUE"]


# ─── Orders ───────────────────────────────────────────────────────────────────

def create_order(user_id: int, chat_id: int, username: str,
                 product_type: str, plan_name: str, amount: int,
                 payment_method: str = "") -> Dict:
    ws = get_sheet("orders")
    headers = SHEET_SCHEMAS["orders"]
    order_id = "ORD-" + _gen_id()
    now = _now()

    # Expiry based on product
    from lib.config import VPN_ORDER_EXPIRY_HOURS, MANUAL_ORDER_EXPIRY_HOURS
    if product_type.upper() == "VPN":
        hours = VPN_ORDER_EXPIRY_HOURS
    else:
        hours = MANUAL_ORDER_EXPIRY_HOURS
    expires_at = (datetime.utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    row = {h: "" for h in headers}
    row.update({
        "order_id": order_id,
        "user_id": user_id,
        "chat_id": chat_id,
        "username": username or "",
        "product_type": product_type,
        "plan_name": plan_name,
        "amount": amount,
        "status": "pending",
        "payment_method": payment_method,
        "created_at": now,
        "expires_at": expires_at,
    })
    ws.append_row([row[h] for h in headers])
    return row


def get_order(order_id: str) -> Optional[Dict]:
    records = _sheet_to_dicts(get_sheet("orders"))
    for r in records:
        if r.get("order_id") == order_id:
            return r
    return None


def get_pending_orders() -> List[Dict]:
    records = _sheet_to_dicts(get_sheet("orders"))
    return [r for r in records if r.get("status") == "pending" and r.get("screenshot_file_id")]


def get_user_orders(user_id: int) -> List[Dict]:
    records = _sheet_to_dicts(get_sheet("orders"))
    return [r for r in records if str(r.get("user_id")) == str(user_id)]


def update_order(order_id: str, **kwargs):
    ws = get_sheet("orders")
    headers = SHEET_SCHEMAS["orders"]
    row_idx = _find_row(ws, "order_id", order_id, headers)
    if not row_idx:
        return
    for key, value in kwargs.items():
        if key in headers:
            col = headers.index(key) + 1
            ws.update_cell(row_idx, col, value)


def attach_screenshot(order_id: str, file_id: str, payment_method: str):
    update_order(order_id, screenshot_file_id=file_id,
                 payment_method=payment_method, status="awaiting_review")


def approve_order(order_id: str, admin_note: str = "") -> Optional[Dict]:
    update_order(order_id, status="approved",
                 admin_note=admin_note, verified_at=_now())
    return get_order(order_id)


def decline_order(order_id: str, admin_note: str = ""):
    update_order(order_id, status="declined",
                 admin_note=admin_note, verified_at=_now())


def expire_old_orders():
    """Mark unsubmitted orders as expired."""
    ws = get_sheet("orders")
    headers = SHEET_SCHEMAS["orders"]
    records = _sheet_to_dicts(ws)
    now = datetime.utcnow()
    for r in records:
        if r.get("status") != "pending":
            continue
        expires_at_str = r.get("expires_at", "")
        if not expires_at_str:
            continue
        try:
            exp = datetime.strptime(str(expires_at_str), "%Y-%m-%d %H:%M:%S")
            if now > exp:
                update_order(r["order_id"], status="expired")
        except Exception:
            pass


# ─── Subscriptions ────────────────────────────────────────────────────────────

def create_subscription(user_id: int, chat_id: int, product_type: str,
                        plan_name: str, days: int, key_or_link: str = "",
                        email: str = "", data_limit_gb: int = 0,
                        order_id: str = "", username: str = "") -> Dict:
    ws = get_sheet("subscriptions")
    headers = SHEET_SCHEMAS["subscriptions"]
    sub_id = "SUB-" + _gen_id()
    expiry = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    row = {h: "" for h in headers}
    row.update({
        "id": sub_id,
        "user_id": user_id,
        "chat_id": chat_id,
        "username": username,
        "product_type": product_type,
        "plan_name": plan_name,
        "expiry_date": expiry,
        "status": "active",
        "key_or_link": key_or_link,
        "email": email,
        "data_limit_gb": data_limit_gb,
        "data_used_gb": 0,
        "reminder_3day_sent": "FALSE",
        "reminder_1day_sent": "FALSE",
        "reminder_0day_sent": "FALSE",
        "created_at": _now(),
    })
    ws.append_row([row[h] for h in headers])

    # Link subscription to order
    if order_id:
        update_order(order_id, subscription_id=sub_id, status="completed")

    return row


def get_user_subscriptions(user_id: int) -> List[Dict]:
    records = _sheet_to_dicts(get_sheet("subscriptions"))
    return [r for r in records if str(r.get("user_id")) == str(user_id)
            and r.get("status") == "active"]


def is_renewal_eligible(user_id: int, product_type: str) -> bool:
    """
    Return True if the user qualifies for a renewal discount price.
    Eligible when they have an active subscription OR one that expired
    within the last 3 days for the given product type.
    """
    records = _sheet_to_dicts(get_sheet("subscriptions"))
    cutoff = datetime.utcnow() - timedelta(days=3)
    for r in records:
        if str(r.get("user_id")) != str(user_id):
            continue
        if r.get("product_type", "").upper() != product_type.upper():
            continue
        expiry_raw = str(r.get("expiry_date", ""))[:10]
        if not expiry_raw:
            continue
        try:
            expiry_dt = datetime.strptime(expiry_raw, "%Y-%m-%d")
            if expiry_dt >= cutoff:   # active or expired ≤ 3 days ago
                return True
        except ValueError:
            pass
    return False


def get_all_active_subscriptions() -> List[Dict]:
    records = _sheet_to_dicts(get_sheet("subscriptions"))
    return [r for r in records if r.get("status") == "active"]


def update_subscription(sub_id: str, **kwargs):
    ws = get_sheet("subscriptions")
    headers = SHEET_SCHEMAS["subscriptions"]
    row_idx = _find_row(ws, "id", sub_id, headers)
    if not row_idx:
        return
    for key, value in kwargs.items():
        if key in headers:
            col = headers.index(key) + 1
            ws.update_cell(row_idx, col, value)


def expire_subscription(sub_id: str):
    update_subscription(sub_id, status="expired")


# ─── Coupons ──────────────────────────────────────────────────────────────────

def get_coupon(code: str) -> Optional[Dict]:
    records = _sheet_to_dicts(get_sheet("coupons"))
    for r in records:
        if str(r.get("code", "")).upper() == code.upper():
            return r
    return None


def get_all_coupons() -> List[Dict]:
    return _sheet_to_dicts(get_sheet("coupons"))


def create_coupon(code: str, product_type: str, plan_name: str, days: int,
                  max_uses: int = 1, expires_at: str = "") -> Dict:
    ws = get_sheet("coupons")
    headers = SHEET_SCHEMAS["coupons"]
    row = {h: "" for h in headers}
    row.update({
        "code": code.upper(),
        "product_type": product_type,
        "plan_name": plan_name,
        "days": days,
        "discount_pct": 100,
        "max_uses": max_uses,
        "used_count": 0,
        "is_active": "TRUE",
        "created_at": _now(),
        "expires_at": expires_at,
    })
    ws.append_row([row[h] for h in headers])
    return row


def use_coupon(code: str, user_id: int, sub_id: str) -> bool:
    ws = get_sheet("coupons")
    headers = SHEET_SCHEMAS["coupons"]
    coupon = get_coupon(code)
    if not coupon:
        return False

    max_uses = int(coupon.get("max_uses", 1) or 1)
    used = int(coupon.get("used_count", 0) or 0)
    if used >= max_uses:
        return False

    row_idx = _find_row(ws, "code", code.upper(), headers)
    if row_idx:
        col = headers.index("used_count") + 1
        ws.update_cell(row_idx, col, used + 1)
        if used + 1 >= max_uses:
            ac_col = headers.index("is_active") + 1
            ws.update_cell(row_idx, ac_col, "FALSE")

    # Log use
    use_ws = get_sheet("coupon_uses")
    use_headers = SHEET_SCHEMAS["coupon_uses"]
    use_row = {h: "" for h in use_headers}
    use_row.update({
        "id": _gen_id(),
        "code": code.upper(),
        "user_id": user_id,
        "used_at": _now(),
        "subscription_id": sub_id,
    })
    use_ws.append_row([use_row[h] for h in use_headers])
    return True


def has_used_coupon(code: str, user_id: int) -> bool:
    records = _sheet_to_dicts(get_sheet("coupon_uses"))
    for r in records:
        if str(r.get("code", "")).upper() == code.upper() and \
           str(r.get("user_id")) == str(user_id):
            return True
    return False


# ─── Rate Limiting ────────────────────────────────────────────────────────────

def check_rate_limit(user_id: int, limit_seconds: int = 3) -> bool:
    """Returns True if allowed, False if rate-limited."""
    ws = get_sheet("rate_limits")
    headers = SHEET_SCHEMAS["rate_limits"]
    records = _sheet_to_dicts(ws)
    now = datetime.utcnow()

    for r in records:
        if str(r.get("user_id")) == str(user_id):
            last_str = r.get("last_request_at", "")
            try:
                last = datetime.strptime(str(last_str), "%Y-%m-%d %H:%M:%S")
                if (now - last).total_seconds() < limit_seconds:
                    return False
                # Update timestamp
                row_idx = _find_row(ws, "user_id", user_id, headers)
                if row_idx:
                    col = headers.index("last_request_at") + 1
                    ws.update_cell(row_idx, col, now.strftime("%Y-%m-%d %H:%M:%S"))
            except Exception:
                pass
            return True

    # New user - insert
    row = [str(user_id), now.strftime("%Y-%m-%d %H:%M:%S")]
    ws.append_row(row)
    return True


# ─── Stats / Reports ──────────────────────────────────────────────────────────

def get_stats() -> Dict:
    users = get_all_users()
    orders = _sheet_to_dicts(get_sheet("orders"))
    subs = get_all_active_subscriptions()

    total_users = len(users)
    total_orders = len(orders)
    approved = [o for o in orders if o.get("status") == "approved"]
    pending = [o for o in orders if o.get("status") in ("pending", "awaiting_review")]
    active_subs = len(subs)

    revenue = sum(int(o.get("amount", 0) or 0) for o in approved)

    # Today's orders
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_orders = [o for o in approved if str(o.get("verified_at", "")).startswith(today)]
    today_revenue = sum(int(o.get("amount", 0) or 0) for o in today_orders)

    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "approved_orders": len(approved),
        "pending_orders": len(pending),
        "active_subscriptions": active_subs,
        "total_revenue": revenue,
        "today_orders": len(today_orders),
        "today_revenue": today_revenue,
    }


# ─── System Config ────────────────────────────────────────────────────────────

def get_config(key: str, default: str = "") -> str:
    records = _sheet_to_dicts(get_sheet("system_config"))
    for r in records:
        if r.get("key") == key:
            return str(r.get("value", default))
    return default


def set_config(key: str, value: str):
    ws = get_sheet("system_config")
    headers = SHEET_SCHEMAS["system_config"]
    records = _sheet_to_dicts(ws)
    for r in records:
        if r.get("key") == key:
            row_idx = _find_row(ws, "key", key, headers)
            if row_idx:
                val_col = headers.index("value") + 1
                upd_col = headers.index("updated_at") + 1
                ws.update_cell(row_idx, val_col, value)
                ws.update_cell(row_idx, upd_col, _now())
            return
    ws.append_row([key, value, _now()])


# ─── Manual Order Creation (Admin) ────────────────────────────────────────────

def create_manual_subscription(user_id: int, chat_id: int, username: str,
                                product_type: str, plan_name: str,
                                days: int, key_or_link: str = "",
                                needs_manual_renewal: bool = False) -> Dict:
    """Admin creates a subscription directly, bypassing payment flow."""
    sub = create_subscription(
        user_id=user_id,
        chat_id=chat_id,
        product_type=product_type,
        plan_name=plan_name,
        days=days,
        key_or_link=key_or_link,
    )

    # Create a completed order record for audit trail
    order = create_order(
        user_id=user_id,
        chat_id=chat_id,
        username=username,
        product_type=product_type,
        plan_name=plan_name,
        amount=0,  # Manual — no charge recorded
    )
    update_order(order["order_id"], status="manual", subscription_id=sub["id"])

    # If this is a long plan needing 42-day manual renewal, register it
    if needs_manual_renewal:
        register_manual_renewal(sub["id"], user_id, username,
                                product_type, plan_name, sub["expiry_date"])

    return sub

# ─── Manual Renewal Tracking (41/42-day admin reminders) ────────────────────
# Rule: plans >= 90 days → remind every 41 days
#       plans  < 90 days → remind every 42 days

RENEWAL_INTERVAL_LONG  = 41   # days for plans >= 90 days (3M, 6M, 1Y, etc.)
RENEWAL_INTERVAL_SHORT = 42   # days for shorter plans (28d, 30d, 42d)


def _renewal_interval(plan_days: int) -> int:
    """Return the correct reminder interval based on plan duration."""
    return RENEWAL_INTERVAL_LONG if plan_days >= 90 else RENEWAL_INTERVAL_SHORT


def register_manual_renewal(sub_id: str, user_id: int, username: str,
                             product_type: str, plan_name: str,
                             expiry_date: str, plan_days: int = 0):
    """Register a subscription for admin reminder cycle.
    Uses 41-day interval for long plans (>=90 days), 42-day for shorter."""
    interval = _renewal_interval(plan_days)
    ws = get_sheet("manual_renewals")
    headers = SHEET_SCHEMAS["manual_renewals"]
    now = datetime.utcnow()
    next_remind = (now + timedelta(days=interval)).strftime("%Y-%m-%d %H:%M:%S")

    # Remove old entry if exists
    existing = _find_row(ws, "sub_id", sub_id, headers)
    if existing:
        ws.delete_rows(existing)

    row = {h: "" for h in headers}
    row.update({
        "sub_id": sub_id,
        "user_id": user_id,
        "username": username or "",
        "product_type": product_type,
        "plan_name": plan_name,
        "expiry_date": expiry_date,
        "last_reminded_at": "",
        "next_remind_at": next_remind,
        "is_active": "TRUE",
    })
    ws.append_row([row[h] for h in headers])


def get_manual_renewals_due() -> List[Dict]:
    """Return renewals where next_remind_at <= now AND subscription still active."""
    records = _sheet_to_dicts(get_sheet("manual_renewals"))
    now = datetime.utcnow()
    due = []
    for r in records:
        if str(r.get("is_active", "")).upper() != "TRUE":
            continue
        next_str = r.get("next_remind_at", "")
        if not next_str:
            continue
        try:
            next_dt = datetime.strptime(str(next_str), "%Y-%m-%d %H:%M:%S")
            if now >= next_dt:
                due.append(r)
        except Exception:
            pass
    return due


def mark_manual_renewal_reminded(sub_id: str, plan_days: int = 0):
    """After admin is notified, push next_remind_at forward.
    Uses 41 days for long plans (>=90d), 42 days for shorter plans."""
    interval = _renewal_interval(plan_days)
    ws = get_sheet("manual_renewals")
    headers = SHEET_SCHEMAS["manual_renewals"]
    row_idx = _find_row(ws, "sub_id", sub_id, headers)
    if not row_idx:
        return
    now = datetime.utcnow()
    next_remind = (now + timedelta(days=interval)).strftime("%Y-%m-%d %H:%M:%S")
    last_col = headers.index("last_reminded_at") + 1
    next_col = headers.index("next_remind_at") + 1
    ws.update_cell(row_idx, last_col, now.strftime("%Y-%m-%d %H:%M:%S"))
    ws.update_cell(row_idx, next_col, next_remind)


def deactivate_manual_renewal(sub_id: str):
    """Stop reminders for a subscription (e.g., expired or cancelled)."""
    ws = get_sheet("manual_renewals")
    headers = SHEET_SCHEMAS["manual_renewals"]
    row_idx = _find_row(ws, "sub_id", sub_id, headers)
    if row_idx:
        col = headers.index("is_active") + 1
        ws.update_cell(row_idx, col, "FALSE")


def update_manual_renewal_expiry(sub_id: str, new_expiry: str):
    """Update expiry date after admin has renewed the provider account."""
    ws = get_sheet("manual_renewals")
    headers = SHEET_SCHEMAS["manual_renewals"]
    row_idx = _find_row(ws, "sub_id", sub_id, headers)
    if row_idx:
        col = headers.index("expiry_date") + 1
        ws.update_cell(row_idx, col, new_expiry)
    # Also update subscriptions sheet
    update_subscription(sub_id, expiry_date=new_expiry)


# ─── Bulk Import Helpers ──────────────────────────────────────────────────────

def bulk_import_users(rows: List[Dict]):
    """Import list of user dicts — skips existing user_ids."""
    ws = get_sheet("users")
    headers = SHEET_SCHEMAS["users"]
    existing_ids = {str(r.get("user_id")) for r in _sheet_to_dicts(ws)}
    new_rows = []
    for u in rows:
        if str(u.get("user_id")) in existing_ids:
            continue
        row = {h: "" for h in headers}
        row.update({
            "user_id": u.get("user_id", ""),
            "username": u.get("username", ""),
            "first_name": u.get("first_name", ""),
            "chat_id": u.get("chat_id") or u.get("user_id", ""),
            "joined_at": u.get("joined_at", _now()),
            "last_active": u.get("last_active", _now()),
            "is_blocked": "TRUE" if u.get("is_blocked") else "FALSE",
            "total_orders": u.get("total_orders", 0),
        })
        new_rows.append([row[h] for h in headers])
    if new_rows:
        ws.append_rows(new_rows)
    return len(new_rows)


def bulk_import_subscriptions(rows: List[Dict]):
    """Import list of subscription dicts — skips existing sub IDs."""
    ws = get_sheet("subscriptions")
    headers = SHEET_SCHEMAS["subscriptions"]
    existing_ids = {str(r.get("id")) for r in _sheet_to_dicts(ws)}
    new_rows = []
    for s in rows:
        if str(s.get("id")) in existing_ids:
            continue
        row = {h: "" for h in headers}
        row.update({
            "id": s.get("id", "SUB-" + _gen_id()),
            "user_id": s.get("user_id", ""),
            "chat_id": s.get("chat_id") or s.get("user_id", ""),
            "username": s.get("username", ""),
            "product_type": s.get("product_type", ""),
            "plan_name": s.get("plan_name", ""),
            "expiry_date": s.get("expiry_date", ""),
            "status": s.get("status", "active"),
            "key_or_link": s.get("key_or_link") or s.get("email", ""),
            "email": s.get("email", ""),
            "data_limit_gb": s.get("data_limit_gb", 0),
            "data_used_gb": s.get("data_used_gb", 0),
            "reminder_3day_sent": "FALSE",
            "reminder_1day_sent": "FALSE",
            "reminder_0day_sent": "FALSE",
            "created_at": s.get("created_at", _now()),
        })
        new_rows.append([row[h] for h in headers])
    if new_rows:
        ws.append_rows(new_rows)
    return len(new_rows)

