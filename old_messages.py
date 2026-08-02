WELCOME_MESSAGE = """✦ *Welcome to Khant's Premium Services*

We provide fast, reliable digital tools at competitive prices.

*Available Services*
━━━━━━━━━━━━━━━━━━━
🔐  VPN          Fast & private browsing
🎥  Zoom Pro     Unlimited HD meetings
🎨  Canva Pro    Full creative toolkit
━━━━━━━━━━━━━━━━━━━

Select an option below to get started."""

MAIN_MENU_TEXT = "🏠 *Main Menu*\nHow can we help you today?"

BUY_MENU = "🛒 *Browse Plans*\nSelect a category to view available plans:"

VPN_CATEGORY_TEXT = "🔐 *VPN Plans*\nChoose a plan to secure your connection:"

ZOOM_CATEGORY_TEXT = "🎥 *Zoom Pro Plans*\nChoose a plan for your meetings:"

CANVA_CATEGORY_TEXT = "🎨 *Canva Pro Plans*\nChoose a plan to unlock the full toolkit:"

PAYMENT_INSTRUCTIONS = """💳 *Payment Summary*
━━━━━━━━━━━━━━━━━━━
📦  Plan      {order_details}
💰  Amount    {amount} MMK
━━━━━━━━━━━━━━━━━━━

*Accepted Methods*
{payment_methods}

📸 *Next Step*
Transfer the exact amount and send a screenshot of your payment receipt."""

ORDER_PENDING_MANUAL = """📋 *Order Received*
━━━━━━━━━━━━━━━━━━━
Order ID   `{order_id}`
Status     Under Review
━━━━━━━━━━━━━━━━━━━

Your payment screenshot has been received and is being reviewed. You will be notified once verified.

_Typical review time: a few minutes to 24 hours._"""

ORDER_VERIFIED = """✅ *Payment Confirmed*
━━━━━━━━━━━━━━━━━━━
Order ID   `{order_id}`
Status     Approved
━━━━━━━━━━━━━━━━━━━

{product}

Thank you for your purchase."""

ORDER_DECLINED = """❌ *Payment Not Verified*
━━━━━━━━━━━━━━━━━━━
Order   #{order_id}
Status  Declined
━━━━━━━━━━━━━━━━━━━

We were unable to verify your payment. Please contact support for assistance: {support}"""

MY_SUBSCRIPTIONS_HEADER = "📦 *My Subscriptions*"

NO_SUBSCRIPTIONS = """📦 *No Active Subscriptions*

You have no active subscriptions at this time.
Browse our plans to get started."""

SUBSCRIPTION_DETAIL = "{icon} *{product_name}*\n📊 Usage: {usage_info}\n⏳ Expires: {expiry}\n🔔 Reminders: {reminders_status}"

SUPPORT_MESSAGE = """💬 *Support*
━━━━━━━━━━━━━━━━━━━

For assistance, please reach out to our support team:

👤  {support_username}

We typically respond within a few hours."""

ADMIN_PANEL = "⚙️ *Control Panel*"

ORDER_NOTIFICATION = """🔔 *New Order*
━━━━━━━━━━━━━━━━━━━
Order    `{order_id}`
User     @{username}
Product  {product}
Amount   {price} MMK"""

ERROR_GENERIC = "⚠️ Something went wrong. Please try again or contact support."
ERROR_RATE_LIMIT = "⏳ You are sending requests too quickly. Please wait a moment and try again."
ERROR_INVALID_COUPON = "❌ That coupon code is invalid or has expired."
ERROR_COUPON_CLAIMED = "❌ You have already used this coupon."

SUCCESS_COUPON_CLAIMED = """🎟️ *Coupon Redeemed*
━━━━━━━━━━━━━━━━━━━
Product  {product}
Valid    {expiry_date}
━━━━━━━━━━━━━━━━━━━

Your subscription has been activated."""
