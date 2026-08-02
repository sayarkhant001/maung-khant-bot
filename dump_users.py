import sqlite3
db = sqlite3.connect('bot_data.db')
print(db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()[0])
