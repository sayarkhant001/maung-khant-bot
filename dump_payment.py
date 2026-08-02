import sqlite3

db = sqlite3.connect('bot_data.db')
db.row_factory = sqlite3.Row
rows = db.execute("SELECT * FROM payment_methods").fetchall()

with open('payment_methods_dump.txt', 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(f"ID: {r['id']}\n")
        f.write(f"Name: {r['method_name']}\n")
        f.write(f"Account: {r['account_info']}\n")
        f.write(f"Account Name: {r['account_name']}\n")
        f.write(f"Icon: {r['icon']}\n")
        f.write(f"Note: {r['note']}\n")
        f.write("-" * 40 + "\n")
