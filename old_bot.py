import telebot
from telebot import types
import config
from database import init_db, get_session
from models import User
import messages
from handlers import admin, buy, user, admin_vless
from handlers.admin_vless import register_vless_handlers
from services import reminders, reports, monitor, migration, cleanup
from services.admin_manager import is_admin, init_primary_admin, update_admin_info
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot
bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode='Markdown')

# Register VLESS Handlers
register_vless_handlers(bot)

# Command Handlers
def send_main_menu(bot, chat_id, message_id=None, is_admin_user=False):
    """Helper to send or edit the main menu"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 Browse Plans", callback_data="main_buy"),
        types.InlineKeyboardButton("📦 My Subscriptions", callback_data="main_subscriptions")
    )
    markup.add(
        types.InlineKeyboardButton("🎟️ Redeem Coupon", callback_data="main_coupon"),
        types.InlineKeyboardButton("💬 Support", callback_data="main_support")
    )

    if is_admin_user:
        markup.add(types.InlineKeyboardButton("⚙️ Control Panel", callback_data="main_admin"))
         
    if message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=messages.WELCOME_MESSAGE,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        except Exception:
            pass # Message might be identical
    else:
        bot.send_message(chat_id, messages.WELCOME_MESSAGE, reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command"""
    try:
        is_admin_user = is_admin(message.chat.id)
        # Check if admin
        if is_admin_user:
            update_admin_info(message.chat.id, message.from_user.username, message.from_user.first_name)
            # Continue to show normal menu with admin button
        
        # Regular user flow
        # Register or update user
        session = get_session()
        user_obj = session.query(User).filter_by(chat_id=message.chat.id).first()
        
        if not user_obj:
            user_obj = User(
                chat_id=message.chat.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
            session.add(user_obj)
            session.commit()
            logger.info(f"New user registered: {message.chat.id}")
        
        session.close()
        
        # Setup persistent bottom keyboard
        reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        reply_markup.add("🛒 Browse Plans", "📦 My Subscriptions")
        reply_markup.add("🎟️ Redeem Coupon", "💬 Support")
        if is_admin_user:
            reply_markup.add("⚙️ Control Panel")

        bot.send_message(
            message.chat.id,
            "Menu ready.",
            reply_markup=reply_markup,
            disable_notification=True
        )
        
        # Send welcome message with inline menu
        send_main_menu(bot, message.chat.id, is_admin_user=is_admin_user)

        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        bot.send_message(message.chat.id, messages.ERROR_GENERIC)

@bot.message_handler(commands=['admin'])
def admin_command(message):
    """Handle /admin command"""
    if is_admin(message.chat.id):
        update_admin_info(message.chat.id, message.from_user.username, message.from_user.first_name)
        admin.show_admin_panel(bot, message)
    else:
        bot.send_message(message.chat.id, "⛔ You do not have permission to access the admin panel.")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Handle /help command"""
    help_text = (
        "📖 *Help & Guide*\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "*Main Options*\n"
        "🛒  Browse Plans       — View VPN, Zoom & Canva plans\n"
        "📦  My Subscriptions   — Check active licenses & keys\n"
        "🎟️  Redeem Coupon      — Apply a promotional code\n"
        "💬  Support            — Contact our team\n\n"
        "*How to Purchase*\n"
        "1\\. Tap *Browse Plans* and select a category\n"
        "2\\. Choose your plan\n"
        "3\\. Select a payment method\n"
        "4\\. Complete the transfer and send your receipt screenshot\n"
        "5\\. We will verify and activate your subscription\n\n"
        "_Verification typically takes a few minutes to 24 hours._\n\n"
        "*Support:* {support}\n"
        "━━━━━━━━━━━━━━━━━━━"
    ).format(support=config.SUPPORT_USERNAME)

    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# Admin Commands
@bot.message_handler(commands=['migrate'])
def migrate_command(message):
    """Handle /migrate command to manually trigger migration"""
    if not is_admin(message.chat.id):
        return
        
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "Usage: /migrate <type> <id>\nExample: /migrate outline 1")
            return
            
        server_type = parts[1]
        server_id = int(parts[2])
        
        if migration.trigger_manual_migration(bot, server_type, server_id):
            bot.reply_to(message, f"✅ Migration triggered for {server_type} server {server_id}")
        else:
            bot.reply_to(message, "❌ Failed to trigger migration. Check server type/ID and logs.")
            
    except ValueError:
        bot.reply_to(message, "❌ Invalid ID format.")
    except Exception as e:
        logger.error(f"Error in migrate command: {e}")
        bot.reply_to(message, "❌ Error occurred.")

# Text Message Handlers (Kept for backwards compatibility with old ReplyKeyboard)

@bot.message_handler(func=lambda m: m.text in ("⚙️ Control Panel", "🔐 Admin Panel"))
def admin_panel_button_handler(message):
    """Handle Admin Panel / Control Panel button"""
    if is_admin(message.chat.id):
        admin.show_admin_panel(bot, message)
@bot.message_handler(func=lambda m: m.text and ('🛒 Browse' in m.text or '🛒 Buy' in m.text))
def buy_handler(message):
    """Handle Buy / Browse Plans button"""
    buy.show_buy_menu(bot, message, edit_message_id=None)

@bot.message_handler(func=lambda m: m.text and ('📦 My Subscriptions' in m.text or 'Subscriptions' in m.text))
def subscriptions_handler(message):
    """Handle My Subscriptions button"""
    user.show_my_subscriptions(bot, message, edit_message_id=None)

@bot.message_handler(func=lambda m: m.text and ('🎟️ Redeem Coupon' in m.text or '🎟️ Claim Coupon' in m.text or 'Coupon' in m.text))
def coupon_handler(message):
    """Handle Redeem Coupon button"""
    user.handle_coupon_claim(bot, message)

@bot.message_handler(func=lambda m: m.text and ('💬 Support' in m.text or 'Support' in m.text))
def support_handler(message):
    """Handle Support button"""
    bot.send_message(
        message.chat.id,
        messages.SUPPORT_MESSAGE.format(support_username=config.SUPPORT_USERNAME),
        parse_mode='Markdown'
    )

# User Text Handler (for purchase flow)
@bot.message_handler(func=lambda m: not m.text.startswith('/') and not is_admin(m.chat.id))
def user_text_handler(message):
    """Handle text input from users (for purchase flow)"""
    # Check if user is in a purchase flow
    if message.chat.id in buy.purchase_states:
        buy.handle_purchase_text(bot, message)

# Admin Wizard Message Handlers
@bot.message_handler(content_types=['photo', 'video', 'text'], func=lambda m: is_admin(m.chat.id) and (not m.text or not m.text.startswith('/')))
def admin_msg_handler(message):
    """Handle text and media messages from admin (for wizards)"""
    from handlers import admin_plans, admin_servers, admin_payments, admin_broadcast, admin_generic_plans
    from handlers import admin_management, admin_coupons

    # Check if admin is in the add-admin forward wizard
    if message.chat.id in admin_management.add_admin_states:
        admin_management.handle_add_admin_forward(bot, message)
        return

    # Check coupon creation wizard
    if message.chat.id in admin_coupons.coupon_states:
        admin_coupons.handle_coupon_wizard(bot, message)
        return

    # Check if admin is in a wizard state
    if message.chat.id in admin_plans.admin_states:
        state = admin_plans.admin_states[message.chat.id]
        if state.get('type') == 'add_vpn_plan':
            admin_plans.handle_vpn_plan_wizard(bot, message, state['vpn_type'])
            return
        elif state.get('type') == 'add_zoom_plan':
            admin_plans.handle_zoom_plan_wizard(bot, message)
            return
        elif state.get('type') == 'add_canva_plan':
            admin_plans.handle_canva_plan_wizard(bot, message)
            return
        elif state.get('type') == 'edit_vpn_plan':
            admin_plans.handle_edit_vpn_plan_wizard(bot, message)
            return
        elif state.get('type') == 'edit_zoom_plan':
            admin_plans.handle_edit_zoom_plan_wizard(bot, message)
            return
        elif state.get('type') == 'edit_canva_plan':
            admin_plans.handle_edit_canva_plan_wizard(bot, message)
            return
    
    if message.chat.id in admin_servers.server_states:
        state = admin_servers.server_states[message.chat.id]
        if state.get('type') == 'add_server_ssh':
            admin_servers.handle_server_ssh_wizard(bot, message)
            return
        elif state.get('type') == 'add_server_manual':
            admin_servers.handle_server_manual_wizard(bot, message)
            return
    
    if message.chat.id in admin_payments.payment_states:
        admin_payments.handle_payment_wizard(bot, message)
        return
    
    if message.chat.id in admin_broadcast.broadcast_states:
        admin_broadcast.handle_broadcast_message(bot, message)
        return
    
    if message.chat.id in admin_generic_plans.generic_plan_states:
        admin_generic_plans.handle_generic_plan_wizard(bot, message)
        return

# Photo Handler (for payment screenshots)
@bot.message_handler(content_types=['photo'])
def photo_handler(message):
    """Handle photo uploads (payment screenshots)"""
    buy.handle_payment_screenshot(bot, message)

# Callback Query Handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Handle all callback queries"""
    try:
        if call.data == 'cancel_state':
            chat_id = call.message.chat.id
            import handlers.admin_servers as s_states
            import handlers.admin_plans as p_states
            import handlers.admin_payments as pay_states
            import handlers.admin_broadcast as b_states
            import handlers.buy as buy_states
            import handlers.admin_generic_plans as gp_states
            
            states = [
                s_states.server_states, p_states.admin_states, pay_states.payment_states,
                b_states.broadcast_states, buy_states.purchase_states, gp_states.generic_plan_states
            ]
            
            for state_dict in states:
                if chat_id in state_dict:
                    del state_dict[chat_id]
                    
            try:
                bot.edit_message_text(
                    "❌ **Action Cancelled**", 
                    chat_id=chat_id, 
                    message_id=call.message.message_id, 
                    parse_mode='Markdown'
                )
            except Exception:
                bot.send_message(chat_id, "❌ **Action Cancelled**", parse_mode='Markdown')
                
            bot.answer_callback_query(call.id, "Action cancelled")
            return

        if call.data == 'main_buy':
            buy.show_buy_menu(bot, call.message, edit_message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
        elif call.data == 'main_subscriptions':
            user.show_my_subscriptions(bot, call.message, edit_message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
        elif call.data == 'main_coupon':
            user.handle_coupon_claim(bot, call.message)
            bot.answer_callback_query(call.id)
        elif call.data == 'main_support':
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=messages.SUPPORT_MESSAGE.format(support_username=config.SUPPORT_USERNAME),
                parse_mode='Markdown',
                reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu"))
            )
            bot.answer_callback_query(call.id)
        elif call.data == 'main_admin':
            if is_admin(call.message.chat.id):
                admin.show_admin_panel(bot, call.message, edit_message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
        elif call.data == 'main_menu':
            send_main_menu(bot, call.message.chat.id, message_id=call.message.message_id, is_admin_user=is_admin(call.message.chat.id))
            bot.answer_callback_query(call.id)
        elif call.data.startswith('admin_') or \
           call.data.startswith('plans_') or \
           call.data.startswith('servers_') or \
           call.data.startswith('srv_arch_') or \
           call.data.startswith('payment_') or \
           call.data.startswith('users_') or \
           call.data.startswith('broadcast_') or \
           call.data.startswith('generic_') or \
           call.data.startswith('report_') or \
           call.data.startswith('coupon_'):
            admin.handle_admin_callback(bot, call)
        elif call.data.startswith('buy_'):
            buy.handle_buy_callback(bot, call)
        elif call.data.startswith('pay_method_'):
            buy.handle_payment_method_selection(bot, call)
        elif call.data.startswith('email_'):
            buy.handle_buy_callback(bot, call)
        elif call.data.startswith('user_'):
            user.handle_user_callback(bot, call)
        elif call.data.startswith('migrate_'):
            if call.data.startswith('migrate_start_'):
                migration.handle_migration_start(bot, call)
            elif call.data.startswith('migrate_select_'):
                migration.handle_migration_select(bot, call)
        elif call.data.startswith('gift_'):
            from handlers.gift import handle_gift_callback
            handle_gift_callback(bot, call)
        elif call.data == 'admin_manual_order' or call.data.startswith('manual_'):
            from handlers import admin_manual
            if call.data == 'admin_manual_order':
                admin_manual.start_manual_order(bot, call.message)
            else:
                admin_manual.handle_manual_callback(bot, call)
    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        bot.answer_callback_query(call.id, "❌ An error occurred while processing your request.", show_alert=True)

def main():
    """Main bot function"""
    try:
        # Initialize database
        
        logger.info("Initializing primary admin...")
        init_primary_admin()
        logger.info("✅ Primary admin initialized")
        logger.info("Initializing database...")
        init_db()
        
        # Setup scheduler for background tasks
        logger.info("Setting up scheduler...")
        scheduler = BackgroundScheduler()
        
        # Check reminders every hour
        scheduler.add_job(
            reminders.check_reminders,
            'interval',
            hours=1,
            args=[bot]
        )
        
        # Expire unverified orders every 6 hours
        scheduler.add_job(
            reminders.expire_unverified_orders,
            'interval',
            hours=1,
            args=[bot]
        )
        
        # Expire ended subscriptions every hour
        scheduler.add_job(
            reminders.expire_subscriptions,
            'interval',
            hours=1,
            args=[bot]
        )
        
        


        
        # Daily sales report (10:30 UTC = 17:00 MMT)
        scheduler.add_job(
            reports.send_daily_sales_report,
            'cron',
            hour=10,
            minute=30,
            args=[bot]
        )
        
        # Server Monitoring (every 3 minutes) - Temporarily disabled due to false positives
        # scheduler.add_job(
        #     monitor.check_server_status,
        #     'interval',
        #     minutes=3,
        #     args=[bot]
        # )
        
        # Migration Check (every hour)
        scheduler.add_job(
            migration.check_server_downtime,
            'interval',
            hours=1,
            args=[bot]
        )
        
        # Auto-cleanup inactive servers (every day at 04:00)
        scheduler.add_job(
            cleanup.auto_cleanup_servers,
            'cron',
            hour=4,
            minute=0,
            args=[bot]
        )
        
        # Weekly active subscriptions report (Sunday 17:30 UTC = Monday 00:00 MMT)
        scheduler.add_job(
            reports.send_active_subscriptions_report,
            'cron',
            day_of_week='sun',
            hour=17,
            minute=30,
            args=[bot]
        )
        
        # Weekly sales report (Sunday 17:30 UTC = Monday 00:00 MMT)
        scheduler.add_job(
            reports.send_weekly_sales_report,
            'cron',
            day_of_week='sun',
            hour=17,
            minute=30,
            args=[bot]
        )

        # Zoom merchant renewal alert — check hourly, fires once on day 27
        # for any Zoom subscription with plan duration > 28 days
        scheduler.add_job(
            reminders.check_zoom_merchant_renewals,
            'interval',
            hours=1,
            args=[bot]
        )

        # Zoom expiry warning — fires once when any Zoom subscription
        # has exactly 1 day left (so admin can renew with merchant)
        scheduler.add_job(
            reminders.check_zoom_expiry_warning,
            'interval',
            hours=1,
            args=[bot]
        )

        scheduler.start()
        logger.info("Scheduler started")
        
        # Start bot
        logger.info("🚀 Bot started successfully!")
        logger.info(f"   Admin ID: {config.ADMIN_ID}")
        logger.info(f"   Support: {config.SUPPORT_USERNAME}")
        
        # Commands menu disabled by user request
        # try:
        #     bot.set_my_commands([
        #         types.BotCommand("start", "🏠 Main Menu"),
        #         types.BotCommand("buy", "🛒 Buy Products"),
        #         types.BotCommand("profile", "👤 My Profile"),
        #         types.BotCommand("help", "🆘 Support"),
        #         types.BotCommand("terms", "📜 Terms & Conditions")
        #     ])
        #     logger.info("✅ Bot commands set successfully")
        # except Exception as e:
        #     logger.error(f"Failed to set commands: {e}")        
        
        # Explicitly delete commands to remove the menu button
        try:
             bot.delete_my_commands()
             logger.info("✅ Bot commands deleted (Menu hidden)")
        except Exception as e:
             logger.error(f"Failed to delete commands: {e}")
        
        bot.infinity_polling()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        scheduler.shutdown()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
