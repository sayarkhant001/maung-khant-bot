"""
Message templates — matches original bot's messages.py
"""

WELCOME_MESSAGE = """✦ *Welcome to Khant's Premium Services*

We provide fast, reliable digital tools at competitive prices.

*Available Services*
━━━━━━━━━━━━━━━━━━━
🎥  Zoom Pro     Unlimited HD meetings
🎨  Canva Pro    Full creative toolkit
━━━━━━━━━━━━━━━━━━━

Select an option below to get started."""

MAIN_MENU_TEXT = "🏠 *Main Menu*\nHow can we help you today?"

BUY_MENU = "🛒 *Browse Plans*\nSelect a category to view available plans:"

ZOOM_CATEGORY_TEXT = "🎥 *Zoom Pro Plans*\nChoose a plan for your meetings:"

CANVA_CATEGORY_TEXT = "🎨 *Canva Pro Plans*\nChoose a plan to unlock the full toolkit:"

PAYMENT_INSTRUCTIONS = """💳 *Payment Summary*
━━━━━━━━━━━━━━━━━━━
📦  Plan      {plan_name}
💰  Amount    {amount}
{email_line}━━━━━━━━━━━━━━━━━━━

*Accepted Methods*
{payment_methods}

📸 *Next Step*
Transfer the exact amount and send a screenshot of your payment receipt."""

ORDER_PENDING_MANUAL = """📋 *Order Received*
━━━━━━━━━━━━━━━━━━━
Order ID   `{order_id}`
Status     Under Review
━━━━━━━━━━━━━━━━━━━

Your payment screenshot has been received and is being reviewed.
You will be notified once verified.

_Typical review time: a few minutes to 24 hours._"""

ORDER_VERIFIED_VPN = """✅ *Payment Confirmed*
━━━━━━━━━━━━━━━━━━━
Order ID   `{order_id}`
Status     Approved
━━━━━━━━━━━━━━━━━━━

🔐 *Your VPN Access Key*
`{key}`

📅 Expires: {expiry}
💾 Data Limit: {data_gb} GB

_Copy the key above and import it in your VPN app._"""

ORDER_VERIFIED_MANUAL = """✅ *Payment Confirmed*
━━━━━━━━━━━━━━━━━━━
Order ID   `{order_id}`
Product    {product}
━━━━━━━━━━━━━━━━━━━

{delivery_info}

Thank you for your purchase! 🎉"""

ORDER_APPROVED_NOTIFICATION = """✅ *Order Approved!*
━━━━━━━━━━━━━━━━━━━
Order ID   `{order_id}`
Status     ✅ *Approved*
━━━━━━━━━━━━━━━━━━━

Your payment has been verified! 🎉
We are preparing your credentials and will send them to you *shortly*.

_Please wait a moment..._"""

ORDER_DECLINED = """❌ *Payment Not Verified*
━━━━━━━━━━━━━━━━━━━
Order   `{order_id}`
Status  Declined
━━━━━━━━━━━━━━━━━━━

We were unable to verify your payment.
Please contact support: {support}"""


MY_SUBSCRIPTIONS_HEADER = "📦 *My Subscriptions*"

NO_SUBSCRIPTIONS = """📦 *No Active Subscriptions*

You have no active subscriptions at this time.
Browse our plans to get started."""

SUPPORT_MESSAGE = """💬 *Support*
━━━━━━━━━━━━━━━━━━━

For assistance, please reach out to our support team:

👤  {support_username}

We typically respond within a few hours."""

ADMIN_PANEL = "⚙️ *Control Panel*"

ORDER_NOTIFICATION = """🔔 *New Order — Payment Submitted*
━━━━━━━━━━━━━━━━━━━
Order    `{order_id}`
User     @{username} (`{user_id}`)
Product  {product}
Plan     {plan_name}
Amount   {amount} MMK
Method   {method}{email_line}
━━━━━━━━━━━━━━━━━━━"""

EMAIL_REQUEST = """📧 *Email Required*
━━━━━━━━━━━━━━━━━━━
Plan: *{plan_name}*

This plan requires an email invite.
Please send your email address:

_Example: yourname@gmail.com_"""

EMAIL_INVALID = "❌ That doesn't look like a valid email. Please try again:"

ERROR_GENERIC = "⚠️ Something went wrong. Please try again or contact support."
ERROR_RATE_LIMIT = "⏳ Please wait a moment before sending another request."
ERROR_INVALID_COUPON = "❌ That coupon code is invalid or has expired."
ERROR_COUPON_CLAIMED = "❌ You have already used this coupon."

MANUAL_ORDER_CREATED = """📋 *Manual Order Created*
━━━━━━━━━━━━━━━━━━━
Order ID      `{order_id}`
Product       {product}
Plan          {plan_name}
Expiry        {expiry}
━━━━━━━━━━━━━━━━━━━

Your subscription has been activated by the admin. ✅"""

MANUAL_RENEWAL_REMINDER = """🔔 *[ADMIN] Manual Renewal Due*
━━━━━━━━━━━━━━━━━━━
User:       @{username} (`{user_id}`)
Product:    {product} — {plan_name}
Sub ID:     `{sub_id}`
Expiry:     {expiry}
Days Left:  {days_left}
━━━━━━━━━━━━━━━━━━━
⚠️ *Action Required:* Go to the provider and renew this account manually.
Next auto-reminder in 42 days (or sooner if expiry ≤ 5 days)."""

SUCCESS_COUPON_CLAIMED = """🎟️ *Coupon Redeemed!*
━━━━━━━━━━━━━━━━━━━
Product  {product}
Plan     {plan_name}
Expires  {expiry_date}
━━━━━━━━━━━━━━━━━━━

Your subscription has been activated! ✅"""

EXPIRY_REMINDER = """⏰ *Subscription Expiry Reminder*

Your *{product}* subscription expires in *{days} days*!

💡 Renewing now will extend your current plan — you won't lose any days!"""

EXPIRY_REMINDER_0 = """⚠️ *Subscription Expired*

Your *{product}* subscription has expired today.

Renew now to continue your service."""
