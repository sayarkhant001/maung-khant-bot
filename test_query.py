import sqlite3
db = sqlite3.connect('bot_data.db')
db.row_factory = sqlite3.Row

# Let's inspect some subscriptions and their related orders
cursor = db.execute("""
    SELECT s.id, s.product_type,
           (SELECT o.product_details FROM orders o WHERE o.subscription_id = s.id LIMIT 1) as order_details,
           (SELECT zp.name FROM zoom_plans zp WHERE zp.id = (SELECT o.plan_id FROM orders o WHERE o.subscription_id = s.id LIMIT 1)) as zoom_plan_name,
           (SELECT vp.days || 'D ' || vp.data_limit_gb || 'GB' FROM vless_plans vp WHERE vp.id = (SELECT o.plan_id FROM orders o WHERE o.subscription_id = s.id LIMIT 1)) as vless_plan_name,
           (SELECT hp.days || 'D ' || hp.data_limit_gb || 'GB' FROM hiddify_plans hp WHERE hp.id = (SELECT o.plan_id FROM orders o WHERE o.subscription_id = s.id LIMIT 1)) as hiddify_plan_name
    FROM subscriptions s
""")

for row in cursor.fetchall():
    print(dict(row))
