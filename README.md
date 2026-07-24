# Telegram Bot — Serverless on Vercel + Google Sheets

Zero-cost replacement for the VPS-based bot. Runs entirely on Vercel's free tier using Google Sheets as the database.

---

## One-Time Setup (Do This Once)

### Step 1 — Google Cloud Service Account

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use existing)
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts** → Create Service Account
5. Give it any name (e.g. `telegram-bot`)
6. Click **Keys → Add Key → Create New Key → JSON**
7. Download the JSON file

### Step 2 — Google Spreadsheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new spreadsheet
2. Name it anything (e.g. `Bot Database`)
3. Copy the Spreadsheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/**SPREADSHEET_ID**/edit`
4. Share the spreadsheet with the service account email (from the JSON file) as **Editor**

### Step 3 — Encode the Service Account JSON

```bash
# On Linux/Mac:
base64 -w 0 service_account.json

# On Windows PowerShell:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("service_account.json"))
```

Copy the output — this is your `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`.

### Step 4 — Create Sheets Tabs

```bash
# Install dependencies locally
pip install -r requirements.txt

# Create .env from template
copy .env.example .env
# Edit .env with your values

# Run setup (creates all sheet tabs + sample data)
python setup_sheets.py
```

### Step 5 — Deploy to Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel --prod
```

Copy your deployment URL (e.g. `https://your-bot.vercel.app`)

### Step 6 — Register Telegram Webhook

```bash
# Replace YOUR_BOT_TOKEN and YOUR_VERCEL_URL
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook?url=https://YOUR_VERCEL_URL/api/webhook"
```

✅ Your bot is now live and free!

---

## Importing Existing Data

Download your SQLite database from the VPS first:

```bash
# On your PC (requires scp or WinSCP)
scp root@139.59.39.218:/root/telegram_bot/bot_data.db ./bot_data.db
```

Then run the import:

```bash
# Preview first (no writes)
python import_subscriptions.py --db bot_data.db --dry-run

# Import all data + register active subs for 42-day renewal tracking
python import_subscriptions.py --db bot_data.db --only-active --mark-renewals
```

---

## Admin Commands

| Command | Description |
|---|---|
| `/admin` | Open admin panel |
| `/manual_order` | Create a manual subscription for a user |

### Admin Panel Features

| Button | What it does |
|---|---|
| 🧾 Pending Orders | Review payment screenshots, approve/decline |
| 📊 Reports | Revenue, orders, user stats |
| 👥 Users | Browse users, block/unblock |
| 📢 Broadcast | Send message to all users |
| 🎟️ Coupons | Create/view gift coupons |
| 📋 Manual Order | Create subscription without payment |
| 🔁 42-Day Renewals | View + mark renewed long-plan subscriptions |

---

## 42-Day Renewal System

When creating a manual order, choose **"Confirm + Track 42-day Renewals"**.

Every 42 days, you (admin) will receive a Telegram message like:

```
🔔 [ADMIN] Manual Renewal Due
━━━━━━━━━━━━━━━━━━━
User:       @customer (12345678)
Product:    ZOOM — Zoom 1 Year
Sub ID:     SUB-ABC123
Expiry:     2027-01-15
Days Left:  180
━━━━━━━━━━━━━━━━━━━
⚠️ Action Required: Go to the provider and renew this account manually.
```

Tap **✅ Mark as Renewed** → enter new expiry date → next reminder auto-schedules.

---

## Adding VPN Later

When ready to add VPN:
1. Add `vpn_plans` rows in Google Sheets
2. Uncomment VPN section in `lib/handlers/buy.py`
3. Add VPN button back to `lib/bot_helpers.py` buy menu
4. Re-deploy with `vercel --prod`

---

## Environment Variables (Vercel Dashboard)

Set these in **Vercel → Project → Settings → Environment Variables**:

| Variable | Description |
|---|---|
| `BOT_TOKEN` | From @BotFather |
| `ADMIN_ID` | Your Telegram user ID |
| `SUPPORT_USERNAME` | e.g. @yoursupport |
| `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` | Base64-encoded service account JSON |
| `GOOGLE_SPREADSHEET_ID` | From the Sheets URL |
| `CRON_SECRET` | Optional: any secret to protect cron endpoint |

---

## Cost: $0/month

| Service | Free Tier |
|---|---|
| Vercel | 100GB-hours/month + unlimited deployments |
| Google Sheets API | 300 req/min, 10M cells |
| Telegram Bot API | Free forever |
