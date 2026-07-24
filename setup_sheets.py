import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

"""
One-time setup: Creates all required Google Sheets tabs with correct headers.
Run this ONCE before deploying the bot.

Usage:
    python setup_sheets.py
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from lib.sheets import get_sheet, SHEET_SCHEMAS

SAMPLE_DATA = {
    "payment_methods": [
        ["1", "KBZPay", "Mobile Wallet", "09XXXXXXXXX", "💳", "TRUE"],
        ["2", "WavePay", "Mobile Wallet", "09XXXXXXXXX", "💰", "TRUE"],
        ["3", "AYA Pay", "Mobile Wallet", "09XXXXXXXXX", "🏦", "TRUE"],
    ],
    "zoom_plans": [
        ["1", "Zoom 1 Month", "30", "5000", "3000", "active", "1"],
        ["2", "Zoom 3 Months", "90", "12000", "8000", "active", "2"],
        ["3", "Zoom 6 Months", "180", "20000", "14000", "active", "3"],
        ["4", "Zoom 1 Year", "365", "35000", "25000", "active", "4"],
    ],
    "canva_plans": [
        ["1", "Canva Pro 1 Month", "30", "4000", "2500", "active", "1"],
        ["2", "Canva Pro 3 Months", "90", "10000", "7000", "active", "2"],
        ["3", "Canva Pro 1 Year", "365", "30000", "20000", "active", "3"],
    ],
}


def main():
    print("=" * 50)
    print("  Google Sheets Setup")
    print("=" * 50)

    for sheet_name, headers in SHEET_SCHEMAS.items():
        try:
            ws = get_sheet(sheet_name)
            print(f"  ✓ {sheet_name} ({len(headers)} columns)")

            # Add sample data for some sheets if empty
            if sheet_name in SAMPLE_DATA:
                existing = ws.get_all_values()
                if len(existing) <= 1:  # Only header row
                    print(f"    → Adding sample data for {sheet_name}...")
                    for row in SAMPLE_DATA[sheet_name]:
                        ws.append_row(row)

        except Exception as e:
            print(f"  ✗ {sheet_name}: {e}")

    print("\n✅ All sheets created!")
    print("\nNext steps:")
    print("  1. Open your Google Spreadsheet and verify the tabs were created")
    print("  2. Update payment_methods with your real account numbers")
    print("  3. Adjust plan prices in zoom_plans and canva_plans")
    print("  4. Deploy to Vercel: vercel --prod")
    print("  5. Register webhook: see README.md")


if __name__ == "__main__":
    main()
