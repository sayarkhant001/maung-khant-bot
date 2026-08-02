#!/usr/bin/env python3
"""
Import current subscriptions from the production SQLite database
into your new Google Sheets database.

Usage:
    1. Download bot_data.db from your VPS:
       (Run on your PC with the db file in the same folder)

    2. Set your env vars in .env (BOT_TOKEN, GOOGLE_*, etc.)

    3. Run:
       python import_subscriptions.py --db bot_data.db

    Options:
       --db PATH          Path to SQLite db file (default: bot_data.db)
       --dry-run          Preview what would be imported without writing
       --only-active      Only import active subscriptions (skip expired)
       --mark-renewals    Auto-register all imported Zoom/Canva subs for
                          42-day renewal tracking
"""
import argparse
import sqlite3
import sys
import os

# Load env from .env file
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from lib import sheets


def connect_db(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        print(f"ERROR: Database file not found: {path}")
        sys.exit(1)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def fmt(val) -> str:
    return str(val) if val is not None else ""


def import_users(conn: sqlite3.Connection, dry_run: bool) -> int:
    cursor = conn.execute("""
        SELECT chat_id as user_id,
               username,
               first_name,
               chat_id,
               created_at as joined_at,
               created_at as last_active,
               is_banned as is_blocked
        FROM users
    """)
    rows = []
    for r in cursor.fetchall():
        rows.append({
            "user_id": r["user_id"],
            "username": fmt(r["username"]),
            "first_name": fmt(r["first_name"]),
            "chat_id": r["chat_id"],
            "joined_at": fmt(r["joined_at"]),
            "last_active": fmt(r["last_active"]),
            "is_blocked": bool(r["is_blocked"]),
            "total_orders": 0,
        })

    print(f"  Found {len(rows)} users in SQLite")
    if dry_run:
        for r in rows[:5]:
            print(f"    [DRY] Would import user: {r['user_id']} @{r['username']}")
        return len(rows)

    count = sheets.bulk_import_users(rows)
    print(f"  Imported {count} new users (skipped duplicates)")
    return count


def import_subscriptions(conn: sqlite3.Connection, dry_run: bool,
                          only_active: bool, mark_renewals: bool) -> int:
    query = """
        SELECT s.id,
               s.chat_id as user_id,
               s.product_type,
               s.status,
               s.expiry_date,
               s.license_key as key_or_link,
               s.email,
               0 as data_limit_gb,
               0 as data_used_gb,
               s.purchase_date as created_at,
               -- Try to get plan name from related tables
               COALESCE(
                   (SELECT zp.name FROM zoom_plans zp WHERE zp.id IN (SELECT o.plan_id FROM orders o WHERE o.subscription_id = s.id LIMIT 1) LIMIT 1),
                   (SELECT cp.name FROM canva_plans cp WHERE cp.id IN (SELECT o.plan_id FROM orders o WHERE o.subscription_id = s.id LIMIT 1) LIMIT 1),
                   (SELECT vp.days || 'D ' || vp.data_limit_gb || 'GB' FROM vless_plans vp WHERE vp.id IN (SELECT o.plan_id FROM orders o WHERE o.subscription_id = s.id LIMIT 1) LIMIT 1),
                   (SELECT hp.days || 'D ' || hp.data_limit_gb || 'GB' FROM hiddify_plans hp WHERE hp.id IN (SELECT o.plan_id FROM orders o WHERE o.subscription_id = s.id LIMIT 1) LIMIT 1),
                   s.product_type
               ) as plan_name,
               -- Get username from users table
               (SELECT u.username FROM users u WHERE u.chat_id = s.chat_id LIMIT 1) as username
        FROM subscriptions s
    """
    if only_active:
        query += " WHERE s.status = 'active'"

    cursor = conn.execute(query)
    rows = []
    renewal_candidates = []

    for r in cursor.fetchall():
        sub_dict = {
            "id": fmt(r["id"]),
            "user_id": r["user_id"],
            "chat_id": r["user_id"],  # chat_id = user_id for private chats
            "username": fmt(r["username"]),
            "product_type": fmt(r["product_type"]).upper(),
            "plan_name": fmt(r["plan_name"]),
            "expiry_date": fmt(r["expiry_date"]),
            "status": fmt(r["status"]),
            "key_or_link": fmt(r["key_or_link"]),
            "email": fmt(r["email"]),
            "data_limit_gb": r["data_limit_gb"] or 0,
            "data_used_gb": r["data_used_gb"] or 0,
            "created_at": fmt(r["created_at"]),
        }
        rows.append(sub_dict)

        # Candidates for 42-day renewal tracking
        if mark_renewals and sub_dict["status"] == "active":
            renewal_candidates.append({
                "sub_id": sub_dict["id"],
                "user_id": sub_dict["user_id"],
                "username": fmt(r["username"]),
                "product_type": sub_dict["product_type"],
                "plan_name": sub_dict["plan_name"],
                "expiry_date": sub_dict["expiry_date"],
            })

    print(f"  Found {len(rows)} subscriptions in SQLite")
    if dry_run:
        for r in rows[:5]:
            print(f"    [DRY] Would import sub: {r['id']} | {r['product_type']} | {r['status']} | expires {r['expiry_date'][:10]}")
        return len(rows)

    count = sheets.bulk_import_subscriptions(rows)
    print(f"  Imported {count} new subscriptions (skipped duplicates)")

    if mark_renewals and renewal_candidates:
        print(f"  Registering {len(renewal_candidates)} subs for 42-day renewal tracking...")
        for rc in renewal_candidates:
            try:
                sheets.register_manual_renewal(
                    sub_id=rc["sub_id"],
                    user_id=rc["user_id"],
                    username=rc["username"],
                    product_type=rc["product_type"],
                    plan_name=rc["plan_name"],
                    expiry_date=rc["expiry_date"],
                )
                print(f"    ✓ {rc['sub_id']} tracked")
            except Exception as e:
                print(f"    ✗ {rc['sub_id']}: {e}")

    return count


def import_zoom_canva_plans(conn: sqlite3.Connection, dry_run: bool):
    """Import Zoom and Canva plans from old DB."""
    # Try zoom_plans
    try:
        cursor = conn.execute("SELECT * FROM zoom_plans")
        plans = cursor.fetchall()
        if plans and not dry_run:
            ws = sheets.get_sheet("zoom_plans")
            headers = sheets.SHEET_SCHEMAS["zoom_plans"]
            existing = {str(r.get("id")) for r in sheets._sheet_to_dicts(ws)}
            new_rows = []
            for i, p in enumerate(plans, 1):
                pid = str(p["id"])
                if pid in existing:
                    continue
                row = [""] * len(headers)
                row[headers.index("id")] = pid
                row[headers.index("name")] = fmt(p["name"] if "name" in p.keys() else f"Zoom Plan {i}")
                row[headers.index("days")] = p["days"] if "days" in p.keys() else 30
                row[headers.index("price")] = p["selling_price"] if "selling_price" in p.keys() else p.get("price", 0)
                row[headers.index("buying_price")] = p["buying_price"] if "buying_price" in p.keys() else 0
                row[headers.index("status")] = "active"
                row[headers.index("sort_order")] = i
                new_rows.append(row)
            if new_rows:
                ws.append_rows(new_rows)
                print(f"  Imported {len(new_rows)} Zoom plans")
        elif dry_run:
            print(f"  [DRY] Would import {len(plans)} Zoom plans")
    except Exception as e:
        print(f"  Note: Could not import zoom_plans: {e}")

    # Try canva_plans
    try:
        cursor = conn.execute("SELECT * FROM canva_plans")
        plans = cursor.fetchall()
        if plans and not dry_run:
            ws = sheets.get_sheet("canva_plans")
            headers = sheets.SHEET_SCHEMAS["canva_plans"]
            existing = {str(r.get("id")) for r in sheets._sheet_to_dicts(ws)}
            new_rows = []
            for i, p in enumerate(plans, 1):
                pid = str(p["id"])
                if pid in existing:
                    continue
                row = [""] * len(headers)
                row[headers.index("id")] = pid
                row[headers.index("name")] = fmt(p["name"] if "name" in p.keys() else f"Canva Plan {i}")
                row[headers.index("days")] = p["days"] if "days" in p.keys() else 30
                row[headers.index("price")] = p["selling_price"] if "selling_price" in p.keys() else p.get("price", 0)
                row[headers.index("buying_price")] = p["buying_price"] if "buying_price" in p.keys() else 0
                row[headers.index("status")] = "active"
                row[headers.index("sort_order")] = i
                new_rows.append(row)
            if new_rows:
                ws.append_rows(new_rows)
                print(f"  Imported {len(new_rows)} Canva plans")
        elif dry_run:
            print(f"  [DRY] Would import {len(plans)} Canva plans")
    except Exception as e:
        print(f"  Note: Could not import canva_plans: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Import current SQLite data into Google Sheets"
    )
    parser.add_argument("--db", default="bot_data.db", help="Path to SQLite db file")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--only-active", action="store_true", help="Only import active subscriptions")
    parser.add_argument("--mark-renewals", action="store_true",
                        help="Register all active Zoom/Canva subs for 42-day renewal tracking")
    args = parser.parse_args()

    print("=" * 55)
    print("  Telegram Bot — SQLite → Google Sheets Import")
    print("=" * 55)
    if args.dry_run:
        print("  [DRY RUN MODE — no data will be written]\n")

    conn = connect_db(args.db)

    print("\n[1] Importing users...")
    try:
        import_users(conn, args.dry_run)
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n[2] Importing Zoom & Canva plans...")
    try:
        import_zoom_canva_plans(conn, args.dry_run)
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n[3] Importing subscriptions...")
    try:
        import_subscriptions(conn, args.dry_run, args.only_active, args.mark_renewals)
    except Exception as e:
        print(f"  ERROR: {e}")

    conn.close()
    print("\n✅ Import complete!")
    print("\nNext: Check your Google Sheets to verify the data looks correct.")
    if args.mark_renewals:
        print("42-day renewal reminders have been registered for active subs.")


if __name__ == "__main__":
    main()
