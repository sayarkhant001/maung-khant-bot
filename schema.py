import sqlite3
db = sqlite3.connect('bot_data.db')
for row in db.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall():
    print(f"Table: {row[0]}")
    print(f"Schema: {row[1]}")
    print("-" * 20)
