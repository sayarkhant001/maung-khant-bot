import sqlite3
import sys
import os

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from lib import sheets

def import_payment_methods():
    conn = sqlite3.connect('bot_data.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM payment_methods")
    
    ws = sheets.get_sheet('payment_methods')
    headers = sheets.SHEET_SCHEMAS['payment_methods']
    
    # We clear the sheet to remove dummy data from setup
    ws.clear()
    ws.append_row(headers)
    
    rows = cursor.fetchall()
    new_rows = []
    
    for r in rows:
        is_active = "TRUE" if str(r["status"]).lower() == "active" else "FALSE"
        
        row_dict = {
            "id": str(r["id"]),
            "name": str(r["method_name"]),
            "type": str(r["method_type"]),
            "account_info": str(r["account_info"]) if r["account_info"] else "",
            "account_name": str(r["account_name"]) if r["account_name"] else "",
            "note": str(r["note"]) if r["note"] else "",
            "icon": str(r["icon"]) if r["icon"] else "",
            "is_active": is_active
        }
        
        row_list = [row_dict.get(h, "") for h in headers]
        new_rows.append(row_list)
        
    if new_rows:
        ws.append_rows(new_rows)
        print(f"Successfully imported {len(new_rows)} payment methods with notes!")
    else:
        print("No payment methods found in SQLite.")

if __name__ == "__main__":
    print("Importing payment methods...")
    import_payment_methods()
