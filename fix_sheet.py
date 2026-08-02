import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from lib import sheets

ws = sheets.get_sheet('subscriptions')
headers = sheets.SHEET_SCHEMAS['subscriptions']
ws.insert_row(headers, index=1)
print("Headers successfully inserted at row 1!")
