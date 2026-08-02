import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from lib import sheets

ws = sheets.get_sheet('subscriptions')
print("Clearing subscriptions sheet...")
ws.clear()
print("Cleared!")
