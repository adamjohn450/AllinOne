#!/usr/bin/env python3
"""
AutoDialer Pro - Telegram Bot
Professional auto-dialing solution via Telegram
"""

import logging
import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

from config import Config
from database import init_db, SessionLocal, User, Campaign, VPSServer, PhoneNumber
from ui_builder import UIBuilder
from vps_manager import VPSManager
from campaign_manager import CampaignManager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states - SIMPLIFIED (No TTS selection needed - using pre-recorded audio)
(SETUP_LICENSE, SETUP_VPS_HOST, SETUP_VPS_PORT, SETUP_VPS_USER, SETUP_VPS_PASS,
 SETUP_AMI_USER, SETUP_AMI_PASS, SETUP_SIP_TYPE, SETUP_SIP_SERVER, SETUP_SIP_USER, 
 SETUP_SIP_PASS, SETUP_GOOGLE_EMAIL, SETUP_GOOGLE_PASS, SETUP_GOOGLE_PHONE,
 CAMPAIGN_NAME, CAMPAIGN_AUDIO, CAMPAIGN_CONCURRENT, CAMPAIGN_PHONES, RENAME_VPS) = range(19)


def get_default_sip_account(db, user_id):
    """Get default SIP account (trunk_majes) for campaigns"""
    from database import SIPAccount
    # Try to get trunk_majes
    sip = db.query(SIPAccount).filter_by(name='trunk_majes').first()
    if not sip:
        # Fallback to any active SIP account
        sip = db.query(SIPAccount).filter_by(is_active=True).first()
    return sip.id if sip else None

class AutoDialerBot:
    """Main bot application"""
    
    def __init__(self):
        self.app = None
        self.campaign_manager = None
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        db = SessionLocal()
        
        try:
            # Check if user exists
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            
            if not db_user:
                # New user - welcome and setup
                await update.message.reply_text(
                    f"👋 **Welcome to AutoDialer Pro!**\n\n"
                    f"Hello {user.first_name}! I'm your professional auto-dialing assistant.\n\n"
                    f"🚀 **Quick Setup:**\n"
                    f"1. Enter your license key\n"
                    f"2. Connect your VPS server\n"
                    f"3. Start making calls!\n\n"
                    f"Let's get started. Please enter your license key:",
                    parse_mode='Markdown'
                )
                return SETUP_LICENSE
            else:
                # Existing user
                db_user.last_active = datetime.utcnow()
                db.commit()
                
                welcome_msg = f"👋 Welcome back, {user.first_name}!\n\n"
                welcome_msg += "What would you like to do today?"
                
                await update.message.reply_text(
                    welcome_msg,
                    reply_markup=UIBuilder.main_menu(),
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
                
        finally:
            db.close()
    
    async def setup_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle license key input"""
        license_key = update.message.text.strip()
        user = update.effective_user
        db = SessionLocal()
        
        try:
            # Validate license (simplified - in production, verify against server)
            if len(license_key) < 10:
                await update.message.reply_text(
                    "❌ Invalid license key. Please try again:"
                )
                return SETUP_LICENSE
            
            # Create user
            db_user = User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                license_key=license_key,
                license_valid_until=datetime.utcnow() + timedelta(days=365),
                max_campaigns=999
            )
            db.add(db_user)
            db.commit()
            
            # Offer VPS setup or skip
            keyboard = [
                [InlineKeyboardButton("✅ Setup VPS Now", callback_data="setup_vps")],
                [InlineKeyboardButton("⏭️ Skip for Later", callback_data="skip_vps")]
            ]
            
            await update.message.reply_text(
                "✅ **License activated successfully!**\n\n"
                "Would you like to connect your VPS server now?\n\n"
                "You can always add it later from the main menu.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return SETUP_VPS_HOST
            
        except Exception as e:
            logger.error(f"License setup error: {e}")
            await update.message.reply_text(
                "❌ An error occurred. Please contact support."
            )
            return ConversationHandler.END
        finally:
            db.close()
    
    async def vps_setup_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VPS setup choice"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "skip_vps":
            await query.edit_message_text(
                "✅ **Setup Complete!**\n\n"
                "You can add your VPS later using /settings\n\n"
                "Use /help to see available commands.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        else:
            await query.edit_message_text(
                "🖥️ **VPS Setup**\n\n"
                "Please enter your VPS IP address or hostname:",
                parse_mode='Markdown'
            )
            return SETUP_VPS_HOST
    
    async def setup_vps_host(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VPS host input"""
        context.user_data['vps_host'] = update.message.text.strip()
        
        await update.message.reply_text(
            "Great! Now enter the SSH port (press Enter for default 22):"
        )
        return SETUP_VPS_PORT
    
    async def setup_vps_port(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VPS port input"""
        port_text = update.message.text.strip()
        context.user_data['vps_port'] = int(port_text) if port_text else 22
        
        await update.message.reply_text(
            "Enter SSH username (usually 'root'):"
        )
        return SETUP_VPS_USER
    
    async def setup_vps_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VPS username input"""
        context.user_data['vps_user'] = update.message.text.strip()
        
        await update.message.reply_text(
            "Enter SSH password:\n"
            "(Your password is encrypted and stored securely)"
        )
        return SETUP_VPS_PASS
    
    async def setup_vps_pass(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VPS password and test connection"""
        context.user_data['vps_pass'] = update.message.text.strip()
        
        # Delete the password message for security
        await update.message.delete()
        
        status_msg = await update.effective_chat.send_message(
            "🔄 Testing VPS connection...",
            parse_mode='Markdown'
        )
        
        # Test connection
        vps = VPSManager(
            host=context.user_data['vps_host'],
            username=context.user_data['vps_user'],
            password=context.user_data['vps_pass'],
            port=context.user_data['vps_port']
        )
        
        if vps.connect():
            await status_msg.edit_text(
                "✅ VPS connection successful!\n\n"
                "Now checking Asterisk installation..."
            )
            
            # Check if Asterisk is installed
            if vps.check_asterisk_installed():
                await status_msg.edit_text(
                    "✅ Asterisk is already installed!\n\n"
                    "Now configuring Asterisk for auto-dialing...\n"
                    "This will set up AMI, dialplan, and other configs."
                )
                
                # Configure Asterisk
                ami_user = 'autodialer'
                ami_pass = vps.generate_random_password()
                
                config_result = vps.configure_asterisk(
                    ami_username=ami_user,
                    ami_password=ami_pass
                )
                
                vps.disconnect()
                
                if config_result.get('success'):
                    # Store credentials for later use
                    context.user_data['ami_user'] = config_result.get('ami_username', ami_user)
                    context.user_data['ami_pass'] = config_result.get('ami_password', ami_pass)
                    
                    await status_msg.edit_text(
                        f"✅ **Asterisk configured successfully!**\n\n"
                        f"Your VPS is ready to make calls!\n\n"
                        f"**AMI Credentials:**\n"
                        f"• Username: `{context.user_data['ami_user']}`\n"
                        f"• Password: `{context.user_data['ami_pass']}`\n\n"
                        f"These have been saved securely.\n\n"
                        f"Completing VPS setup...",
                        parse_mode='Markdown'
                    )
                    
                    # Skip to saving VPS - credentials already set
                    return await self.save_vps_config(update, context)
                else:
                    await status_msg.edit_text(
                        "⚠️ **Asterisk found but configuration failed.**\n\n"
                        "You can configure it manually.\n\n"
                        "Enter AMI username (or type 'cancel' to abort):"
                    )
                    return SETUP_AMI_USER
            else:
                # Offer to install
                keyboard = [
                    [InlineKeyboardButton("✅ Yes, Install Asterisk", callback_data="install_asterisk")],
                    [InlineKeyboardButton("❌ No, I'll Install Manually", callback_data="skip_install")]
                ]
                
                await status_msg.edit_text(
                    "Asterisk is not installed on your VPS.\n\n"
                    "Would you like me to install and configure it automatically?\n"
                    "(This will take about 10-15 minutes)",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                vps.disconnect()
                return SETUP_AMI_USER
        else:
            await status_msg.edit_text(
                "❌ Failed to connect to VPS.\n\n"
                "Please check your credentials and try again.\n\n"
                "Use /start to restart setup."
            )
            vps.disconnect()
            return ConversationHandler.END
    
    async def install_asterisk_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Asterisk installation"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "install_asterisk":
            status_msg = await query.edit_message_text(
                "🔧 **Installing Asterisk...**\n\n"
                "This will take 10-15 minutes. I'll keep you updated!",
                parse_mode='Markdown'
            )
            
            # Install Asterisk
            vps = VPSManager(
                host=context.user_data['vps_host'],
                username=context.user_data['vps_user'],
                password=context.user_data['vps_pass'],
                port=context.user_data['vps_port']
            )
            
            # Note: VPS manager install_asterisk doesn't support async callbacks
            # It runs in a sync context, so we can't use async progress updates
            
            if vps.connect():
                # For now, skip progress callback to avoid asyncio issues
                success = vps.install_asterisk()
                vps.disconnect()
                
                if success:
                    await status_msg.edit_text(
                        "✅ **Asterisk installed successfully!**\n\n"
                        "Your VPS is ready to make calls!\n\n"
                        "Default AMI credentials:\n"
                        "• Username: `autodialer`\n"
                        "• Password: `autodialer_pass_change_me`\n\n"
                        "Please enter AMI username:",
                        parse_mode='Markdown'
                    )
                    return SETUP_AMI_USER
                else:
                    await status_msg.edit_text(
                        "❌ Installation failed.\n\n"
                        "Please install Asterisk manually and use /start to continue."
                    )
                    return ConversationHandler.END
        else:
            await query.edit_message_text(
                "Okay, please install Asterisk manually on your VPS.\n\n"
                "Once installed, enter AMI username:"
            )
            return SETUP_AMI_USER
    
    async def save_vps_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save VPS configuration to database and configure SIP"""
        user = update.effective_user if hasattr(update, 'effective_user') else update.callback_query.from_user
        db = SessionLocal()
        
        try:
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            
            # Prepare SIP data based on type
            sip_type = context.user_data.get('sip_type', 'skip')
            
            vps_data = {
                'user_id': db_user.id,
                'name': "Main Server",
                'host': context.user_data['vps_host'],
                'ssh_port': context.user_data['vps_port'],
                'ssh_username': context.user_data['vps_user'],
                'ssh_password': context.user_data['vps_pass'],
                'ami_port': 5038,
                'ami_username': context.user_data['ami_user'],
                'ami_password': context.user_data['ami_pass'],
                'status': 'ready'
            }
            
            # Add SIP configuration if provided
            if sip_type == 'sip':
                vps_data.update({
                    'sip_type': 'sip',
                    'sip_server': context.user_data.get('sip_server'),
                    'sip_username': context.user_data.get('sip_user'),
                    'sip_password': context.user_data.get('sip_pass'),
                    'sip_port': 5060,
                    'caller_id_name': 'AutoDialer',
                    'caller_id_number': context.user_data.get('sip_user', '1000')
                })
            elif sip_type == 'google':
                vps_data.update({
                    'sip_type': 'google_voice',
                    'google_email': context.user_data.get('google_email'),
                    'google_password': context.user_data.get('google_pass'),
                    'google_phone': context.user_data.get('google_phone'),
                    'caller_id_name': 'AutoDialer',
                    'caller_id_number': context.user_data.get('google_phone', '1000')
                })
            
            vps_server = VPSServer(**vps_data)
            db.add(vps_server)
            db.commit()
            db.refresh(vps_server)
            
            # Configure SIP on Asterisk if SIP was provided
            if sip_type in ['sip', 'google']:
                await self._configure_sip_on_vps(vps_server, sip_type, context)
            
            # Get the message object to reply to
            if hasattr(update, 'message'):
                chat = update.message.chat
            elif hasattr(update, 'callback_query'):
                chat = update.callback_query.message.chat
            else:
                chat = update.effective_chat
            
            # Build success message
            sip_info = ""
            if sip_type == 'sip':
                sip_info = f"\n• SIP: {context.user_data.get('sip_server')}"
            elif sip_type == 'google':
                sip_info = f"\n• Google Voice: {context.user_data.get('google_email')}"
            
            await self.app.bot.send_message(
                chat_id=chat.id,
                text=(
                    "🎉 **Setup Complete!**\n\n"
                    f"Your AutoDialer is ready to use!{sip_info}\n\n"
                    "You can now:\n"
                    "• Create campaigns\n"
                    "• Upload phone lists\n"
                    "• Start making calls\n\n"
                    "Use the menu below to get started:"
                ),
                reply_markup=UIBuilder.main_menu(),
                parse_mode='Markdown'
            )
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"VPS save error: {e}")
            if hasattr(update, 'message'):
                await update.message.reply_text(
                    "❌ An error occurred during setup. Please try again or contact support."
                )
            else:
                await update.callback_query.message.reply_text(
                    "❌ An error occurred during setup. Please try again or contact support."
                )
        finally:
            db.close()
    
    async def _configure_sip_on_vps(self, vps_server, sip_type, context):
        """Configure SIP trunk on Asterisk"""
        try:
            from vps_manager import VPSManager
            
            # Create SIP account object
            class SIPAccountTemp:
                def __init__(self, vps, sip_type):
                    self.name = f"trunk_{vps.id}"
                    self.provider_type = sip_type
                    if sip_type == 'sip':
                        self.sip_server = vps.sip_server
                        self.sip_username = vps.sip_username
                        self.sip_password = vps.sip_password
                        self.sip_port = vps.sip_port or 5060
                    else:  # google_voice
                        self.google_email = vps.google_email
                        self.google_password = vps.google_password
                        self.google_phone = vps.google_phone
            
            sip_account = SIPAccountTemp(vps_server, sip_type)
            
            # Connect to VPS and configure
            vps_mgr = VPSManager(
                host=vps_server.host,
                username=vps_server.ssh_username,
                password=vps_server.ssh_password,
                port=vps_server.ssh_port
            )
            
            if vps_mgr.connect():
                success = vps_mgr.configure_sip_trunks([sip_account])
                vps_mgr.disconnect()
                
                if success:
                    logger.info(f"SIP configured on VPS {vps_server.id}")
                else:
                    logger.warning(f"SIP configuration may have failed on VPS {vps_server.id}")
            
        except Exception as e:
            logger.error(f"Failed to configure SIP on VPS: {e}")
            return ConversationHandler.END
        finally:
            db.close()
    
    async def setup_ami_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle AMI username input"""
        if update.callback_query:
            # Coming from button, ask for input
            await update.callback_query.message.reply_text(
                "Enter AMI username (default: autodialer):"
            )
            return SETUP_AMI_USER
        
        context.user_data['ami_user'] = update.message.text.strip() or 'autodialer'
        
        await update.message.reply_text(
            "Enter AMI password:"
        )
        return SETUP_AMI_PASS
    
    async def setup_ami_pass(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle AMI password and move to SIP setup"""
        user = update.effective_user
        context.user_data['ami_pass'] = update.message.text.strip()
        
        # Delete password message
        await update.message.delete()
        
        # Ask for SIP configuration type
        keyboard = [
            [InlineKeyboardButton("📞 Regular SIP", callback_data="sip_type_sip")],
            [InlineKeyboardButton("🔊 Google Voice", callback_data="sip_type_google")],
            [InlineKeyboardButton("⏭️ Skip (Configure Later)", callback_data="sip_type_skip")]
        ]
        
        await update.effective_chat.send_message(
            "📞 **SIP Configuration**\n\n"
            "Choose how you want to make calls:\n\n"
            "• **Regular SIP**: Use your own SIP provider\n"
            "• **Google Voice**: Use Google Voice (requires credentials)\n"
            "• **Skip**: Configure later from VPS settings",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return SETUP_SIP_TYPE
    
    async def setup_sip_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle SIP type selection"""
        query = update.callback_query
        await query.answer()
        
        sip_type = query.data.replace('sip_type_', '')
        context.user_data['sip_type'] = sip_type
        
        if sip_type == 'skip':
            # Skip SIP setup, save VPS without SIP
            return await self.save_vps_config(update, context)
        elif sip_type == 'sip':
            await query.edit_message_text(
                "📞 **Regular SIP Setup**\n\n"
                "Enter your SIP server URL or IP:\n"
                "(e.g., sip.yourprovider.com or 123.45.67.89)"
            )
            return SETUP_SIP_SERVER
        elif sip_type == 'google':
            await query.edit_message_text(
                "🔊 **Google Voice Setup**\n\n"
                "Enter your Google account email:"
            )
            return SETUP_GOOGLE_EMAIL
    
    async def setup_sip_server(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle SIP server input"""
        context.user_data['sip_server'] = update.message.text.strip()
        
        await update.message.reply_text(
            "Enter your SIP username:"
        )
        return SETUP_SIP_USER
    
    async def setup_sip_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle SIP username input"""
        context.user_data['sip_user'] = update.message.text.strip()
        
        await update.message.reply_text(
            "Enter your SIP password:"
        )
        return SETUP_SIP_PASS
    
    async def setup_sip_pass(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle SIP password and complete setup"""
        context.user_data['sip_pass'] = update.message.text.strip()
        
        # Delete password message
        await update.message.delete()
        
        # Save VPS with SIP config
        return await self.save_vps_config(update, context)
    
    async def setup_google_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Google email input"""
        context.user_data['google_email'] = update.message.text.strip()
        
        await update.message.reply_text(
            "Enter your Google account password:"
        )
        return SETUP_GOOGLE_PASS
    
    async def setup_google_pass(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Google password input"""
        context.user_data['google_pass'] = update.message.text.strip()
        
        # Delete password message
        await update.message.delete()
        
        await update.effective_chat.send_message(
            "Enter your Google Voice phone number:\n"
            "(e.g., +1234567890)"
        )
        return SETUP_GOOGLE_PHONE
    
    async def setup_google_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Google Voice phone and complete setup"""
        context.user_data['google_phone'] = update.message.text.strip()
        
        # Save VPS with Google Voice config
        return await self.save_vps_config(update, context)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = update.effective_user
        
        # Debug logging
        logger.info(f"Button clicked: {data} by user {user.id}")
        
        # Main menu
        if data == "main_menu":
            await query.edit_message_text(
                "🏠 **Main Menu**\n\nWhat would you like to do?",
                reply_markup=UIBuilder.main_menu(),
                parse_mode='Markdown'
            )
        
        # Help
        elif data == "help":
            help_text = """
📚 **AutoDialer Pro - Help**

**Main Commands:**
/start - Main menu
/help - Show this help
/stats - View statistics
/addvps - Add VPS server
/newcampaign - Create new campaign

**Features:**
• Manage VPS servers
• Configure SIP accounts
• Create campaigns
• View call statistics
• Manage phone lists

Need support? Contact @support
"""
            await query.edit_message_text(
                help_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
        
        # My Campaigns
        elif data == "my_campaigns":
            await self.show_campaigns(query, user.id)
        
        # New Campaign
        elif data == "new_campaign":
            await query.edit_message_text(
                "📞 **Create New Campaign**\n\n"
                "Use the /newcampaign command to create a campaign.\n\n"
                "This will start a step-by-step wizard.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
        
        # VPS Servers
        elif data == "vps_servers":
            await self.show_vps_servers(query, user.id)
        
        # Add VPS - This is handled by separate conversation handler
        # The button doesn't need a handler here as it's an entry point
        
        # Statistics
        elif data == "statistics":
            await self.show_statistics(query, user.id)
        
        # Settings
        elif data == "settings":
            await query.edit_message_text(
                "⚙️ **Settings**\n\nChoose an option:",
                reply_markup=UIBuilder.settings_menu(),
                parse_mode='Markdown'
            )
        
        # Settings submenu handlers
        elif data == "settings_notifications":
            await query.edit_message_text(
                "🔔 **Notification Settings**\n\n"
                "Configure when you want to receive notifications:\n\n"
                "• ✅ Campaign started\n"
                "• ✅ Call transferred (press 1)\n"
                "• ✅ Callback requested (press 2)\n"
                "• ✅ Campaign completed\n"
                "• ✅ VPS connection issues\n\n"
                "All notifications are currently enabled.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]]),
                parse_mode='Markdown'
            )
        
        elif data == "settings_license":
            db = SessionLocal()
            try:
                db_user = db.query(User).filter_by(telegram_id=user.id).first()
                if db_user:
                    license_info = f"""
🔐 **License Information**

**License Key:** `{db_user.license_key}`
**Valid Until:** {db_user.license_valid_until.strftime('%Y-%m-%d') if db_user.license_valid_until else 'N/A'}
**Max Campaigns:** {db_user.max_campaigns}

**Status:** {'✅ Active' if db_user.license_valid_until and db_user.license_valid_until > datetime.utcnow() else '❌ Expired'}
"""
                    await query.edit_message_text(
                        license_info,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]]),
                        parse_mode='Markdown'
                    )
            finally:
                db.close()
        
        elif data == "settings_profile":
            db = SessionLocal()
            try:
                db_user = db.query(User).filter_by(telegram_id=user.id).first()
                if db_user:
                    profile_info = f"""
👤 **Profile Information**

**Name:** {db_user.first_name}
**Username:** @{db_user.username if db_user.username else 'N/A'}
**Telegram ID:** `{db_user.telegram_id}`
**Member Since:** {db_user.created_at.strftime('%Y-%m-%d')}
**Last Active:** {db_user.last_active.strftime('%Y-%m-%d %H:%M') if db_user.last_active else 'N/A'}
"""
                    await query.edit_message_text(
                        profile_info,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]]),
                        parse_mode='Markdown'
                    )
            finally:
                db.close()
        
        elif data == "settings_telegram":
            await query.edit_message_text(
                "📱 **Telegram Settings**\n\n"
                "**Bot Configuration:**\n"
                "• Language: English\n"
                "• Timezone: UTC\n"
                "• Response Time: Instant\n\n"
                "Contact support to customize these settings.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="settings")]]),
                parse_mode='Markdown'
            )
        
        elif data == "settings_sip":
            db = SessionLocal()
            try:
                db_user = db.query(User).filter_by(telegram_id=user.id).first()
                from database import SIPAccount
                sip_accounts = db.query(SIPAccount).filter_by(user_id=db_user.id).all()
                
                if sip_accounts:
                    sip_list = "\n".join([
                        f"• {acc.name} ({acc.provider_type}) - {'✅ Active' if acc.is_active else '❌ Inactive'}"
                        for acc in sip_accounts
                    ])
                    message = f"📞 **Your SIP Accounts**\n\n{sip_list}\n\n"
                else:
                    message = "📞 **SIP Accounts**\n\nYou don't have any SIP accounts yet.\n\n"
                
                message += "**Options:**\n• Add custom SIP account\n• Connect Google Voice\n• Buy SIP from us\n\nUse /addsip to add a new account."
                
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ Add SIP", callback_data="add_sip")],
                        [InlineKeyboardButton("📱 Google Voice", callback_data="add_google_voice")],
                        [InlineKeyboardButton("🛒 Buy SIP", callback_data="settings_buy_sip")],
                        [InlineKeyboardButton("🔙 Back", callback_data="settings")]
                    ]),
                    parse_mode='Markdown'
                )
            finally:
                db.close()
        
        elif data == "settings_buy_sip":
            await query.edit_message_text(
                "🛒 **Buy SIP Service**\n\n"
                "Professional SIP trunking for your campaigns:\n\n"
                "**Features:**\n"
                "✅ Unlimited concurrent calls\n"
                "✅ Premium call quality\n"
                "✅ Caller ID customization\n"
                "✅ US & Canada coverage\n"
                "✅ Instant activation\n\n"
                "**Pricing:**\n"
                "• Basic: $49/month (10 lines)\n"
                "• Pro: $99/month (25 lines)\n"
                "• Enterprise: $199/month (100 lines)\n\n"
                "Contact @support to purchase.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Contact Support", url="https://t.me/support")],
                    [InlineKeyboardButton("🔙 Back", callback_data="settings")]
                ]),
                parse_mode='Markdown'
            )
        
        # Cancel button
        elif data == "cancel":
            await query.edit_message_text(
                "❌ **Cancelled**\n\nOperation cancelled.",
                reply_markup=UIBuilder.main_menu(),
                parse_mode='Markdown'
            )
        
        # VPS actions - MUST come before campaign actions to avoid conflicts!
        # Order matters! Most specific patterns first
        elif data.startswith("confirm_delete_vps_"):
            logger.info(f"Confirm delete VPS handler triggered for: {data}")
            server_id = int(data.split("_")[3])
            await self.delete_vps_confirmed(query, user.id, server_id)
        
        elif data.startswith("delete_vps_"):
            server_id = int(data.split("_")[2])
            await self.delete_vps(query, user.id, server_id)
        
        elif data.startswith("vps_status_"):
            server_id = int(data.split("_")[2])
            await self.show_vps_status(query, user.id, server_id)
        
        elif data.startswith("test_vps_"):
            server_id = int(data.split("_")[2])
            await self.test_vps_connection(query, user.id, server_id)
        
        elif data.startswith("test_call_"):
            server_id = int(data.split("_")[2])
            await self.test_call(query, user.id, server_id)
        
        elif data.startswith("config_vps_"):
            server_id = int(data.split("_")[2])
            await self.configure_vps(query, user.id, server_id)
        
        elif data.startswith("edit_sip_"):
            server_id = int(data.split("_")[2])
            await query.answer("📞 SIP configuration coming soon! Use /addvps to set up a new server with SIP.")
        
        elif data.startswith("edit_gv_"):
            server_id = int(data.split("_")[2])
            await query.answer("🔊 Google Voice configuration coming soon! Use /addvps to set up a new server.")
        
        elif data.startswith("rename_vps_"):
            server_id = int(data.split("_")[2])
            # Store server ID and ask for new name
            db = SessionLocal()
            try:
                user_db = db.query(User).filter_by(telegram_id=user.id).first()
                server = db.query(VPSServer).filter_by(id=server_id, user_id=user_db.id).first()
                if server:
                    context.user_data['rename_server_id'] = server_id
                    await query.edit_message_text(
                        f"📝 **Rename VPS Server**\n\n"
                        f"Current name: **{server.name or server.host}**\n\n"
                        f"Send me the new name for this server:",
                        parse_mode='Markdown'
                    )
                else:
                    await query.answer("❌ Server not found")
            finally:
                db.close()
        
        elif data.startswith("vps_"):
            server_id = int(data.split("_")[1])
            # Show VPS details
            db = SessionLocal()
            try:
                server = db.query(VPSServer).filter_by(id=server_id).first()
                if server:
                    status_emoji = {
                        'pending': '⏳',
                        'installing': '🔧',
                        'ready': '✅',
                        'error': '❌'
                    }.get(server.status, '❔')
                    
                    vps_info = f"""
🖥️ **VPS Server Details**

**Name:** {server.name or 'Unnamed'}
**Host:** {server.host}
**Status:** {status_emoji} {server.status.upper()}

**SSH Configuration:**
• Port: {server.ssh_port}
• Username: {server.ssh_username}

**AMI Configuration:**
• Port: {server.ami_port}
• Username: {server.ami_username}

**Created:** {server.created_at.strftime('%Y-%m-%d %H:%M')}
"""
                    await query.edit_message_text(
                        vps_info,
                        reply_markup=UIBuilder.vps_control_menu(server),
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        "❌ VPS server not found.",
                        reply_markup=UIBuilder.main_menu()
                    )
            finally:
                db.close()
        
        # Campaign control actions - Come AFTER VPS actions
        elif data.startswith("start_"):
            campaign_id = int(data.split("_")[1])
            await self.start_campaign_action(query, user.id, campaign_id)
        
        elif data.startswith("pause_"):
            campaign_id = int(data.split("_")[1])
            await self.pause_campaign_action(query, user.id, campaign_id)
        
        elif data.startswith("resume_"):
            campaign_id = int(data.split("_")[1])
            await self.resume_campaign_action(query, user.id, campaign_id)
        
        elif data.startswith("stop_"):
            campaign_id = int(data.split("_")[1])
            await self.stop_campaign_action(query, user.id, campaign_id)
        
        elif data.startswith("stats_"):
            campaign_id = int(data.split("_")[1])
            await self.show_campaign_stats(query, user.id, campaign_id)
        
        elif data.startswith("campaign_"):
            campaign_id = int(data.split("_")[1])
            await self.show_campaign_details(query, user.id, campaign_id)
        
        # Additional campaign actions
        elif data.startswith("confirm_delete_campaign_"):
            campaign_id = int(data.split("_")[3])
            await self.delete_campaign_confirmed(query, user.id, campaign_id)
        
        elif data.startswith("delete_campaign_"):
            campaign_id = int(data.split("_")[2])
            await self.delete_campaign(query, user.id, campaign_id)
        
        elif data.startswith("logs_"):
            campaign_id = int(data.split("_")[1])
            await self.show_campaign_logs(query, user.id, campaign_id)
        
        elif data.startswith("delete_") and not data.startswith("delete_campaign_") and not data.startswith("delete_vps_"):
            campaign_id = int(data.split("_")[1])
            await self.delete_campaign(query, user.id, campaign_id)
    
    async def show_campaigns(self, query, user_id):
        """Show user's campaigns"""
        db = SessionLocal()
        try:
            db_user = db.query(User).filter_by(telegram_id=user_id).first()
            campaigns = db_user.campaigns[-10:]  # Last 10
            
            if campaigns:
                await query.edit_message_text(
                    "📋 **Your Campaigns**\n\nSelect a campaign:",
                    reply_markup=UIBuilder.campaign_list_menu(campaigns),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "📋 **Your Campaigns**\n\n"
                    "You don't have any campaigns yet.\n"
                    "Click 'New Campaign' to create one!",
                    reply_markup=UIBuilder.main_menu(),
                    parse_mode='Markdown'
                )
        finally:
            db.close()
    
    async def show_campaign_details(self, query, user_id, campaign_id):
        """Show campaign details"""
        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter_by(id=campaign_id).first()
            
            if campaign and campaign.user.telegram_id == user_id:
                # Get stats
                stats = await self.campaign_manager.get_campaign_stats(campaign_id)
                
                message = UIBuilder.format_campaign_info(campaign, stats)
                
                await query.edit_message_text(
                    text=message,
                    reply_markup=UIBuilder.campaign_control_menu(campaign),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "❌ Campaign not found.",
                    reply_markup=UIBuilder.main_menu()
                )
        finally:
            db.close()
    
    async def start_campaign_action(self, query, user_id, campaign_id):
        """Start a campaign"""
        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter_by(id=campaign_id).first()
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if campaign and campaign.user_id == user.id:
                # Get VPS config
                server = db.query(VPSServer).filter_by(id=campaign.server_id or user.servers[0].id).first()
                
                vps_config = {
                    'host': server.host,
                    'ami_port': server.ami_port,
                    'ami_username': server.ami_username,
                    'ami_password': server.ami_password
                }
                
                #Start campaign
                success = await self.campaign_manager.start_campaign(campaign_id, vps_config)
                
                if success:
                    await query.edit_message_text(
                        f"✅ **Campaign Started!**\n\n"
                        f"Campaign '{campaign.name}' is now running.\n"
                        f"You'll receive notifications for transfers and callbacks.",
                        reply_markup=UIBuilder.campaign_control_menu(campaign),
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        f"❌ Failed to start campaign.\nPlease check your VPS connection.",
                        reply_markup=UIBuilder.campaign_control_menu(campaign),
                        parse_mode='Markdown'
                    )
        finally:
            db.close()
    
    async def pause_campaign_action(self, query, user_id, campaign_id):
        """Pause a campaign"""
        await self.campaign_manager.pause_campaign(campaign_id)
        await query.answer("Campaign paused")
        await self.show_campaign_details(query, user_id, campaign_id)
    
    async def resume_campaign_action(self, query, user_id, campaign_id):
        """Resume a campaign"""
        await self.campaign_manager.resume_campaign(campaign_id)
        await query.answer("Campaign resumed")
        await self.show_campaign_details(query, user_id, campaign_id)
    
    async def stop_campaign_action(self, query, user_id, campaign_id):
        """Stop a campaign"""
        await self.campaign_manager.stop_campaign(campaign_id)
        await query.answer("Campaign stopped")
        await self.show_campaign_details(query, user_id, campaign_id)
    
    async def delete_campaign(self, query, user_id, campaign_id):
        """Show campaign delete confirmation"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            campaign = db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()
            
            if not campaign:
                await query.answer("❌ Campaign not found")
                return
            
            # Check if campaignhas phone numbers
            from database import PhoneNumber
            phone_count = db.query(PhoneNumber).filter_by(campaign_id=campaign_id).count()
            
            warning = ""
            if campaign.status == 'running':
                warning = "\n\n⚠️ **Warning:** Campaign is currently running! It will be stopped."
            
            if phone_count > 0:
                warning += f"\n⚠️ **{phone_count} phone numbers** and all call logs will be deleted."
            
            await query.edit_message_text(
                f"🗑️ **Delete Campaign**\n\n"
                f"Are you sure you want to delete **{campaign.name}**?{warning}\n\n"
                f"This action cannot be undone.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_campaign_{campaign_id}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data=f"campaign_{campaign_id}")]
                ]),
                parse_mode='Markdown'
            )
        finally:
            db.close()
    
    async def delete_campaign_confirmed(self, query, user_id, campaign_id):
        """Delete campaign"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            campaign = db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()
            
            if not campaign:
                await query.answer("❌ Campaign not found")
                return
            
            campaign_name = campaign.name
            
            # Stop campaign if running
            if campaign.status == 'running':
                await self.campaign_manager.stop_campaign(campaign_id)
            
            # Delete associated data
            from database import PhoneNumber, CallLog
            db.query(PhoneNumber).filter_by(campaign_id=campaign_id).delete()
            db.query(CallLog).filter_by(campaign_id=campaign_id).delete()
            
            # Delete campaign
            db.delete(campaign)
            db.commit()
            
            await query.edit_message_text(
                "✅ **Campaign Deleted**\n\n"
                f"Campaign **{campaign_name}** has been removed along with all associated data.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Campaigns", callback_data="my_campaigns")]]),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Delete campaign error: {e}")
            db.rollback()
            await query.edit_message_text(
                f"❌ **Delete Failed**\n\n{str(e)[:200]}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="my_campaigns")]]),
                parse_mode='Markdown'
            )
        finally:
            db.close()
    
    async def show_campaign_logs(self, query, user_id, campaign_id):
        """Send campaign call logs as a CSV/text file"""
        import io
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            campaign = db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()

            if not campaign:
                await query.answer("❌ Campaign not found")
                return

            from database import CallLog
            logs = db.query(CallLog).filter_by(campaign_id=campaign_id).order_by(CallLog.timestamp.asc()).all()

            if not logs:
                await query.answer("No call logs yet.")
                return

            # Build CSV content
            lines = ["phone_number,status,duration_sec,timestamp,notes"]
            for log in logs:
                ts = log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else ''
                duration = log.duration or 0
                notes = (log.notes or '').replace(',', ';')
                lines.append(f"{log.phone_number},{log.status},{duration},{ts},{notes}")

            content = "\n".join(lines)
            file_bytes = io.BytesIO(content.encode('utf-8'))
            file_bytes.name = f"{campaign.name}_logs.csv"

            await query.message.reply_document(
                document=file_bytes,
                filename=f"{campaign.name}_logs.csv",
                caption=f"📋 Call logs for **{campaign.name}** — {len(logs)} records",
                parse_mode='Markdown'
            )
            await query.answer("✅ Logs sent!")
        except Exception as e:
            logger.error(f"show_campaign_logs error: {e}")
            await query.answer(f"❌ Error: {str(e)[:100]}")
        finally:
            db.close()
    
    async def show_campaign_stats(self, query, user_id, campaign_id):
        """Show detailed campaign statistics"""
        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter_by(id=campaign_id).first()
            
            if campaign and campaign.user.telegram_id == user_id:
                stats = await self.campaign_manager.get_campaign_stats(campaign_id)
                
                progress = UIBuilder.progress_bar(stats.get('attempted', 0), stats.get('total', 0))
                
                message = f"""
📊 **Campaign Statistics**

**{campaign.name}**

📞 **Progress:** {stats.get('attempted', 0)}/{stats.get('total', 0)} dialed
{progress}

**Calls:**
• Total: {stats.get('total', 0)}
• Dialed: {stats.get('attempted', 0)}
• Active Now: {stats.get('active', 0)}
• Pending: {stats.get('pending', 0)}
• No Answer: {stats.get('no_answer', 0)}
• Failed: {stats.get('failed', 0)}

**Results:**
• Pressed 1 (Callbacks): {stats.get('callbacks', 0)}

**Success Rate:** {stats.get('success_rate', 0):.1f}%
"""
                
                await query.edit_message_text(
                    message,
                    reply_markup=UIBuilder.campaign_control_menu(campaign),
                    parse_mode='Markdown'
                )
        finally:
            db.close()
    
    async def show_vps_servers(self, query, user_id):
        """Show VPS servers"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            servers = user.servers
            
            if servers:
                await query.edit_message_text(
                    "🖥️ **VPS Servers**\n\nYour configured servers:",
                    reply_markup=UIBuilder.vps_list_menu(servers),
                    parse_mode='Markdown'
                )
            else:
                keyboard = [
                    [InlineKeyboardButton("➕ Add VPS Server", callback_data="add_vps")],
                    [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
                ]
                await query.edit_message_text(
                    "🖥️ **VPS Servers**\n\n"
                    "No servers configured yet.\n\n"
                    "Click the button below or use /addvps to add your first server.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        finally:
            db.close()
    
    async def test_vps_connection(self, query, user_id, server_id):
        """Test VPS connection"""
        db = SessionLocal()
        try:
            server = db.query(VPSServer).filter_by(id=server_id, user_id=db.query(User).filter_by(telegram_id=user_id).first().id).first()
            if not server:
                await query.answer("❌ Server not found")
                return
            
            await query.answer("🔄 Testing connection...")
            
            # Test SSH connection
            vps = VPSManager(server.host, server.ssh_username, server.ssh_password, port=server.ssh_port)
            ssh_status = "✅ Connected" if vps.connect() else "❌ Failed"
            
            # Test AMI connection if SSH works
            ami_status = "⏩ Skipped"
            if vps.client:
                result = vps.execute_command(f"echo 'test' | nc -w 1 localhost {server.ami_port}")
                ami_status = "✅ Port Open" if result['success'] else "❌ Port Closed"
                vps.disconnect()
            
            result_msg = f"""
🔄 **Connection Test Results**

**Server:** {server.host}

**SSH Connection:** {ssh_status}
**AMI Port ({server.ami_port}):** {ami_status}

**Test completed at:** {datetime.now().strftime('%H:%M:%S')}
"""
            await query.edit_message_text(
                result_msg,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Test Again", callback_data=f"test_vps_{server_id}")],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"vps_{server_id}")]
                ]),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Test VPS error: {e}")
            await query.answer(f"❌ Test failed: {str(e)}")
        finally:
            db.close()
    
    async def test_call(self, query, user_id, server_id):
        """Test SIP trunk with a real call"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            server = db.query(VPSServer).filter_by(id=server_id, user_id=user.id).first()
            if not server:
                await query.answer("❌ Server not found")
                return
            
            # Check if server has SIP configuration
            if not server.sip_server or not server.sip_username:
                await query.edit_message_text(
                    "❌ **SIP Configuration Missing**\n\n"
                    "Please configure SIP settings first.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⚙️ Configure SIP", callback_data=f"config_vps_{server_id}")],
                        [InlineKeyboardButton("🔙 Back", callback_data=f"vps_{server_id}")]
                    ]),
                    parse_mode='Markdown'
                )
                return
            
            await query.answer("📞 Making test call...")
            
            # Use a default test number (user's phone from campaigns if available)
            test_number = "12633783363"  # Default test number
            
            # Try to get user's phone from recent campaigns
            campaign = db.query(Campaign).filter_by(user_id=user.id).order_by(Campaign.created_at.desc()).first()
            if campaign:
                phone = db.query(PhoneNumber).filter_by(campaign_id=campaign.id).first()
                if phone:
                    test_number = phone.phone_number
            
            # Make test call via SSH
            vps = VPSManager(server.host, server.ssh_username, server.ssh_password, port=server.ssh_port)
            if not vps.connect():
                await query.edit_message_text(
                    "❌ **Connection Failed**\n\n"
                    f"Could not connect to VPS {server.host}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back", callback_data=f"vps_{server_id}")]
                    ]),
                    parse_mode='Markdown'
                )
                return
            
            # Check SIP registration
            sip_check = vps.execute_command("asterisk -rx 'pjsip show registrations'")
            sip_status = "Unknown"
            if sip_check['success']:
                output = sip_check['output']
                if 'Registered' in output:
                    sip_status = "✅ Registered"
                elif 'Rejected' in output or 'Unregistered' in output:
                    sip_status = "❌ Not Registered"
            
            # Make the test call
            call_cmd = f"asterisk -rx 'channel originate PJSIP/{test_number}@trunk_2 application Playback demo-congrats'"
            result = vps.execute_command(call_cmd)
            
            vps.disconnect()
            
            call_status = "✅ Call initiated" if result['success'] else "❌ Call failed"
            
            result_msg = f"""
📞 **Test Call Results**

**VPS:** {server.name or server.host}
**SIP Server:** {server.sip_server}
**SIP Status:** {sip_status}

**Test Number:** {test_number}
**Call Status:** {call_status}

{result['output'][:200] if result.get('output') else ''}

**Time:** {datetime.now().strftime('%H:%M:%S')}
"""
            await query.edit_message_text(
                result_msg,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 Test Again", callback_data=f"test_call_{server_id}")],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"vps_{server_id}")]
                ]),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Test call error: {e}")
            await query.edit_message_text(
                f"❌ **Test Failed**\n\n{str(e)}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data=f"vps_{server_id}")]
                ]),
                parse_mode='Markdown'
            )
        finally:
            db.close()
    
    async def show_vps_status(self, query, user_id, server_id):
        """Show detailed VPS status"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            server = db.query(VPSServer).filter_by(id=server_id, user_id=user.id).first()
            if not server:
                await query.answer("❌ Server not found")
                return
            
            # Count campaigns using this server
            campaigns = db.query(Campaign).filter_by(server_id=server_id).count()
            active_campaigns = db.query(Campaign).filter_by(server_id=server_id, status='running').count()
            
            sip_info = ""
            if server.sip_type == 'sip' and server.sip_server:
                sip_info = f"\n**SIP Server:** {server.sip_server}"
            elif server.sip_type == 'google_voice' and server.google_email:
                sip_info = f"\n**Google Voice:** {server.google_email}"
            
            status_msg = f"""
📊 **VPS Status Report**

**Server:** {server.name or 'Unnamed'}
**Host:** {server.host}
**Status:** {server.status.upper()}

**Campaigns:**
• Total: {campaigns}
•Active: {active_campaigns}

**Configuration:**{sip_info}
**AMI:** {server.ami_username}@localhost:{server.ami_port}
**Asterisk:** {server.asterisk_version or 'Unknown version'}

**Uptime:** Since {server.created_at.strftime('%Y-%m-%d')}
"""
            await query.edit_message_text(
                status_msg,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data=f"vps_{server_id}")]
                ]),
                parse_mode='Markdown'
            )
        finally:
            db.close()
    
    async def configure_vps(self, query, user_id, server_id):
        """Configure VPS SIP settings"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            server = db.query(VPSServer).filter_by(id=server_id, user_id=user.id).first()
            if not server:
                await query.answer("❌ Server not found")
                return
            
            sip_status = "Not configured"
            if server.sip_type == 'sip' and server.sip_server:
                sip_status = f"SIP: {server.sip_server}"
            elif server.sip_type == 'google_voice' and server.google_email:
                sip_status = f"Google Voice: {server.google_email}"
            
            config_msg = f"""
⚙️ **Configure VPS**

**Server:** {server.name or 'Unnamed'}
**Current SIP:** {sip_status}

**What would you like to configure?**
"""
            await query.edit_message_text(
                config_msg,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 Change SIP", callback_data=f"edit_sip_{server_id}")],
                    [InlineKeyboardButton("🔊 Setup Google Voice", callback_data=f"edit_gv_{server_id}")],
                    [InlineKeyboardButton("📝 Rename Server", callback_data=f"rename_vps_{server_id}")],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"vps_{server_id}")]
                ]),
                parse_mode='Markdown'
            )
        finally:
            db.close()
    
    async def rename_vps_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VPS rename message"""
        # Only process if in rename mode
        if 'rename_server_id' not in context.user_data:
            return
        
        user = update.effective_user
        new_name = update.message.text.strip()
        server_id = context.user_data.pop('rename_server_id')  # Remove flag
        
        db = SessionLocal()
        try:
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            server = db.query(VPSServer).filter_by(id=server_id, user_id=db_user.id).first()
            
            if not server:
                await update.message.reply_text("❌ Server not found.", reply_markup=UIBuilder.main_menu())
                return
            
            old_name = server.name or server.host
            server.name = new_name
            db.commit()
            
            await update.message.reply_text(
                f"✅ **Server Renamed Successfully**\n\n"
                f"**Old name:** {old_name}\n"
                f"**New name:** {new_name}",
                reply_markup=UIBuilder.main_menu(),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Rename VPS error: {e}")
            await update.message.reply_text(f"❌ Failed to rename: {str(e)}", reply_markup=UIBuilder.main_menu())
        finally:
            db.close()
    
    async def delete_vps(self, query, user_id, server_id):
        """Show VPS delete confirmation"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            server = db.query(VPSServer).filter_by(id=server_id, user_id=user.id).first()
            if not server:
                await query.answer("❌ Server not found")
                return
            
            # Check if any campaigns use this server
            campaigns = db.query(Campaign).filter_by(server_id=server_id).count()
            
            warning = ""
            if campaigns > 0:
                warning = f"\n\n⚠️ **Warning:** This server has {campaigns} campaign(s). They will be stopped."
            
            await query.edit_message_text(
                f"🗑️ **Delete VPS Server**\n\n"
                f"Are you sure you want to delete **{server.name or server.host}**?{warning}\n\n"
                f"This action cannot be undone.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_vps_{server_id}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data=f"vps_{server_id}")]
                ]),
                parse_mode='Markdown'
            )
        finally:
            db.close()
    
    async def delete_vps_confirmed(self, query, user_id, server_id):
        """Delete VPS server"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            server = db.query(VPSServer).filter_by(id=server_id, user_id=user.id).first()
            if not server:
                await query.answer("❌ Server not found")
                return
            
            server_name = server.name or server.host
            
            # Stop all campaigns using this server and detach them
            campaigns = db.query(Campaign).filter_by(server_id=server_id).all()
            for campaign in campaigns:
                campaign.status = 'stopped'
                campaign.server_id = None  # Detach from server to avoid FK violation
            
            # Commit the campaign changes first
            db.commit()
            
            # Now delete the server
            db.delete(server)
            db.commit()
            
            await query.edit_message_text(
                "✅ **VPS Server Deleted**\n\n"
                f"Server **{server_name}** has been removed.\n\n"
                f"{'✅ ' + str(len(campaigns)) + ' campaign(s) stopped and detached.' if campaigns else ''}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Servers", callback_data="vps_servers")]]),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Delete VPS error: {e}")
            db.rollback()
            # Truncate error message to fit Telegram's 200 char limit
            error_msg = str(e)[:150]
            await query.edit_message_text(
                f"❌ **Delete Failed**\n\n{error_msg}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="vps_servers")]]),
                parse_mode='Markdown'
            )
        finally:
            db.close()
    
    async def show_statistics(self, query, user_id):
        """Show user statistics"""
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            total_campaigns = len(user.campaigns)
            active_campaigns = db.query(Campaign).filter_by(user_id=user.id, status='running').count()
            completed_campaigns = db.query(Campaign).filter_by(user_id=user.id, status='completed').count()
            
            # Get call stats
            from database import CallLog
            total_calls = db.query(CallLog).join(Campaign).filter(Campaign.user_id == user.id).count()
            successful_calls = db.query(CallLog).join(Campaign).filter(
                Campaign.user_id == user.id,
                CallLog.status.in_(['transferred', 'callback', 'completed'])
            ).count()
            transfers = db.query(CallLog).join(Campaign).filter(
                Campaign.user_id == user.id,
                CallLog.status == 'transferred'
            ).count()
            callbacks = db.query(CallLog).join(Campaign).filter(
                Campaign.user_id == user.id,
                CallLog.status == 'callback'
            ).count()
            
            stats = {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'completed_campaigns': completed_campaigns,
                'total_calls': total_calls,
                'successful_calls': successful_calls,
                'failed_calls': total_calls - successful_calls,
                'transfers': transfers,
                'callbacks': callbacks,
                'max_campaigns': user.max_campaigns,
                'license_valid_until': user.license_valid_until.strftime('%Y-%m-%d') if user.license_valid_until else 'N/A'
            }
            
            message = UIBuilder.format_statistics(stats)
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
        finally:
            db.close()
    
    async def newcampaign_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start new campaign creation"""
        user = update.effective_user
        db = SessionLocal()
        
        try:
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            
            if not db_user:
                await update.message.reply_text("Please use /start to register first.")
                return
            
            # Check if user has VPS configured
            if not db_user.servers:
                await update.message.reply_text(
                    "❌ **No VPS Server Configured**\n\n"
                    "You need to add a VPS server before creating campaigns.\n\n"
                    "Use /addvps to add your VPS server.",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
            
            await update.message.reply_text(
                "📞 **Create New Campaign**\n\n"
                "Let's create your campaign step by step.\n\n"
                "First, what would you like to name this campaign?\n"
                "(e.g., 'Tax Season 2026', 'Account Verification')",
                parse_mode='Markdown'
            )
            return CAMPAIGN_NAME
            
        finally:
            db.close()
    
    async def campaign_name_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle campaign name input"""
        campaign_name = update.message.text.strip()
        
        if len(campaign_name) < 3:
            await update.message.reply_text(
                "❌ Campaign name must be at least 3 characters.\n\n"
                "Please enter a campaign name:"
            )
            return CAMPAIGN_NAME
        
        context.user_data['campaign_name'] = campaign_name
        
        # Show audio template selection
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = [
            [InlineKeyboardButton("🇨🇦 CRA Crypto", callback_data="audio_cracrypto")],
            [InlineKeyboardButton("💱 Ndax", callback_data="audio_ndax")],
            [InlineKeyboardButton("🏦 CIBC", callback_data="audio_cibc")],
            [InlineKeyboardButton("🏦 TD Bank", callback_data="audio_td")],
            [InlineKeyboardButton("🏦 National Bank", callback_data="audio_nat")],
            [InlineKeyboardButton("🏦 RBC", callback_data="audio_rbc")],
            [InlineKeyboardButton("💰 Coinbase", callback_data="audio_coinbase")],
            [InlineKeyboardButton("💰 Binance", callback_data="audio_binance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Campaign name: **{campaign_name}**\n\n"
            "📢 **Select Audio Template:**\n\n"
            "Choose which pre-recorded message to play during calls:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return CAMPAIGN_AUDIO
    
    async def campaign_audio_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle audio template selection"""
        query = update.callback_query
        await query.answer()
        
        # Extract audio template from callback data
        audio_template = query.data.replace('audio_', '')
        context.user_data['audio_template'] = audio_template
        
        # Map template names to display names
        audio_names = {
            'cracrypto': 'CRA Crypto',
            'ndax': 'Ndax',
            'cibc': 'CIBC',
            'td': 'TD Bank',
            'nat': 'National Bank',
            'rbc': 'RBC',
            'coinbase': 'Coinbase',
            'binance': 'Binance'
        }
        
        audio_display = audio_names.get(audio_template, audio_template.upper())
        
        await query.edit_message_text(
            f"✅ Campaign: **{context.user_data.get('campaign_name')}**\n"
            f"🔊 Audio: **{audio_display}**\n\n"
            "📞 **Concurrent Calls**\n\n"
            "How many calls should run simultaneously?\n"
            "Enter a number between **1-30**:\n\n"
            "💡 Tip: 10-20 is recommended. Higher values may cause SIP provider rejections.",
            parse_mode='Markdown'
        )
        return CAMPAIGN_CONCURRENT
    
    async def campaign_concurrent_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle concurrent calls input"""
        try:
            concurrent = int(update.message.text.strip())
            
            if concurrent < 1 or concurrent > 30:
                await update.message.reply_text(
                    "❌ Please enter a number between 1 and 30."
                )
                return CAMPAIGN_CONCURRENT
            
            context.user_data['max_concurrent'] = concurrent
            
            await update.message.reply_text(
                f"✅ Campaign: **{context.user_data.get('campaign_name')}**\n"
                f"🔊 Audio: **{context.user_data.get('audio_template', 'cracrypto')}**\n"
                f"📞 Concurrent Calls: **{concurrent}**\n\n"
                "Now, upload your phone list.\n\n"
                "**Options:**\n"
                "• Send a text file (.txt) with one phone number per line\n"
                "• Type numbers separated by commas",
                parse_mode='Markdown'
            )
            return CAMPAIGN_PHONES
            
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a valid number between 1 and 30."
            )
            return CAMPAIGN_CONCURRENT
    
    async def campaign_phones_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle phone list upload and create campaign"""
        phone_numbers = []
        
        # Check if it's a file
        if update.message.document:
            file = await update.message.document.get_file()
            file_content = await file.download_as_bytearray()
            
            try:
                content = file_content.decode('utf-8')
                phone_numbers = [line.strip() for line in content.split('\n') if line.strip()]
            except:
                await update.message.reply_text(
                    "❌ Failed to read file. Please send a text file with one number per line."
                )
                return CAMPAIGN_PHONES
        
        # Check if it's text
        elif update.message.text:
            text = update.message.text.strip()
            # Split by comma or newline
            phone_numbers = [p.strip() for p in text.replace(',', '\n').split('\n') if p.strip()]
        
        if not phone_numbers:
            await update.message.reply_text(
                "❌ No phone numbers found.\n\n"
                "Please send a file or type phone numbers (comma-separated):"
            )
            return CAMPAIGN_PHONES
        
        # Store phone numbers
        context.user_data['phone_numbers'] = phone_numbers
        
        # Create campaign immediately with default concurrent = 5
        await update.message.reply_text(
            f"⏳ Creating campaign with **{len(phone_numbers)}** phone numbers...",
            parse_mode='Markdown'
        )
        
        # Create campaign in database
        user = update.effective_user
        db = SessionLocal()
        
        try:
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            
            # Get first VPS server
            if not db_user.servers:
                await update.message.reply_text(
                    "❌ No VPS server found. Please set up a VPS first using /setup",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
            
            server = db_user.servers[0]
            
            # Get selected audio template and concurrent calls
            audio_template = context.user_data.get('audio_template', 'cracrypto')
            max_concurrent = context.user_data.get('max_concurrent', 5)
            
            # Create campaign
            campaign = Campaign(
                user_id=db_user.id,
                server_id=server.id,
                name=context.user_data['campaign_name'],
                tts_transfer=audio_template,  # Store audio template name
                tts_callback='',  # No callback message needed
                transfer_number='',  # No transfer number needed
                max_concurrent=max_concurrent,
                total_numbers=len(phone_numbers),
                status='pending',
                sip_account_id=get_default_sip_account(db, db_user.id)
            )
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            
            # Add phone numbers
            for phone in phone_numbers:
                phone_record = PhoneNumber(
                    campaign_id=campaign.id,
                    phone_number=phone,
                    status='pending'
                )
                db.add(phone_record)
            
            db.commit()
            
            # Generate TTS audio
            from generate_tts import generate_campaign_tts
            await asyncio.to_thread(generate_campaign_tts, campaign.id, server.host, server.ssh_username, server.ssh_password, server.ssh_port)
            
            await update.message.reply_text(
                "✅ **Campaign Created!**\n\n"
                f"📝 Name: **{campaign.name}**\n"
                f"📞 Numbers: **{len(phone_numbers)}**\n"
                f"🔄 Max Concurrent: **{campaign.max_concurrent} calls**\n\n"
                "Campaign is ready! Use /campaigns to view and start it.",
                parse_mode='Markdown',
                reply_markup=UIBuilder.main_menu()
            )
            
            # Clear user data
            context.user_data.clear()
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Failed to create campaign: {e}")
            await update.message.reply_text(
                f"❌ Failed to create campaign:\n{str(e)}\n\nPlease try again.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
            
        finally:
            db.close()
    
    async def addvps_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start VPS setup for existing users"""
        user = update.effective_user if update.message else update.callback_query.from_user
        db = SessionLocal()
        
        try:
            # Log that we're starting
            logger.info(f"addvps_start called for user {user.id}")
            
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            
            if not db_user:
                if update.message:
                    await update.message.reply_text(
                        "Please use /start to register first."
                    )
                else:
                    await update.callback_query.answer("Please use /start first", show_alert=True)
                return ConversationHandler.END
            
            message_text = (
                "🖥️ **Add VPS Server**\n\n"
                "Let's connect your VPS server!\n\n"
                "Please enter your VPS IP address or hostname:"
            )
            
            if update.message:
                # Called via command
                await update.message.reply_text(message_text, parse_mode='Markdown')
            else:
                # Called via button - must answer callback first
                await update.callback_query.answer()
                try:
                    await update.callback_query.edit_message_text(message_text, parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"Error editing message in addvps_start: {e}")
                    # If edit fails, send new message
                    await update.callback_query.message.reply_text(message_text, parse_mode='Markdown')
            
            logger.info(f"addvps_start: returning SETUP_VPS_HOST state")
            return SETUP_VPS_HOST
            
        except Exception as e:
            logger.error(f"Error in addvps_start: {e}")
            if update.callback_query:
                await update.callback_query.answer("Error starting VPS setup", show_alert=True)
            return ConversationHandler.END
        finally:
            db.close()
    
    async def cancel_vps_setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel VPS setup"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ **VPS setup cancelled.**\n\n"
            "You can add a VPS later using /addvps",
            reply_markup=UIBuilder.main_menu(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    async def cancel_campaign(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel campaign creation"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ **Campaign creation cancelled.**\n\n"
            "Use /newcampaign to start again.",
            reply_markup=UIBuilder.main_menu(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    async def send_telegram_message(self, user_id, message):
        """Send message to user"""
        try:
            await self.app.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
    
    def run(self):
        """Run the bot"""
        # Initialize database
        init_db()
        
        # Create application
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Initialize campaign manager
        db = SessionLocal()
        self.campaign_manager = CampaignManager(db)
        self.campaign_manager.set_telegram_callback(self.send_telegram_message)
        
        # Setup conversation handler
        setup_conv = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                SETUP_LICENSE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_license),
                    CallbackQueryHandler(self.vps_setup_choice, pattern="^(setup_vps|skip_vps)$")
                ],
                SETUP_VPS_HOST: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_vps_host),
                    CallbackQueryHandler(self.vps_setup_choice, pattern="^(setup_vps|skip_vps)$")
                ],
                SETUP_VPS_PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_vps_port)],
                SETUP_VPS_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_vps_user)],
                SETUP_VPS_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_vps_pass)],
                SETUP_AMI_USER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_ami_user),
                    CallbackQueryHandler(self.install_asterisk_callback, pattern="^(install_asterisk|skip_install)$")
                ],
                SETUP_AMI_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_ami_pass)],
                SETUP_SIP_TYPE: [CallbackQueryHandler(self.setup_sip_type, pattern="^sip_type_")],
                SETUP_SIP_SERVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_sip_server)],
                SETUP_SIP_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_sip_user)],
                SETUP_SIP_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_sip_pass)],
                SETUP_GOOGLE_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_google_email)],
                SETUP_GOOGLE_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_google_pass)],
                SETUP_GOOGLE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_google_phone)],
            },
            fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
            per_message=False
        )
        
        # Campaign creation conversation handler - SIMPLIFIED (No TTS selection)
        campaign_conv = ConversationHandler(
            entry_points=[CommandHandler('newcampaign', self.newcampaign_start)],
            states={
                CAMPAIGN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.campaign_name_handler)],
                CAMPAIGN_AUDIO: [CallbackQueryHandler(self.campaign_audio_handler, pattern='^audio_')],
                CAMPAIGN_CONCURRENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.campaign_concurrent_handler)],
                CAMPAIGN_PHONES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.campaign_phones_handler),
                    MessageHandler(filters.Document.ALL, self.campaign_phones_handler)
                ]
            },
            fallbacks=[CommandHandler('cancel', self.cancel_campaign)],
            per_message=False
        )
        
        # Add VPS conversation handler (for existing users)
        addvps_conv = ConversationHandler(
            entry_points=[
                CommandHandler('addvps', self.addvps_start),
                CallbackQueryHandler(self.addvps_start, pattern="^add_vps$")
            ],
            states={
                SETUP_VPS_HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_vps_host)],
                SETUP_VPS_PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_vps_port)],
                SETUP_VPS_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_vps_user)],
                SETUP_VPS_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_vps_pass)],
                SETUP_AMI_USER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_ami_user),
                    CallbackQueryHandler(self.install_asterisk_callback, pattern="^(install_asterisk|skip_install)$")
                ],
                SETUP_AMI_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_ami_pass)],
                SETUP_SIP_TYPE: [CallbackQueryHandler(self.setup_sip_type, pattern="^sip_type_")],
                SETUP_SIP_SERVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_sip_server)],
                SETUP_SIP_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_sip_user)],
                SETUP_SIP_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_sip_pass)],
                SETUP_GOOGLE_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_google_email)],
                SETUP_GOOGLE_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_google_pass)],
                SETUP_GOOGLE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.setup_google_phone)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_vps_setup)],
            per_message=False,
            allow_reentry=True
        )
        
        # Add handlers - Order matters! Specific handlers before general ones
        self.app.add_handler(setup_conv)
        self.app.add_handler(campaign_conv)
        self.app.add_handler(addvps_conv)
        self.app.add_handler(CommandHandler('help', self.help_command))
        self.app.add_handler(CommandHandler('stats', self.stats_command))
        # Rename handler (checks for rename mode in user_data)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.rename_vps_handler))
        # General button handler MUST be last to not intercept conversation buttons
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Start bot
        logger.info("🚀 AutoDialer Bot starting...")
        self.app.run_polling()
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message"""
        help_text = """
📚 **AutoDialer Pro - Help**

**Main Commands:**
/start - Main menu
/help - Show this help
/stats - View statistics
/addvps - Add VPS server
/newcampaign - Create new campaign
/settings - Bot settings

**Features:**
• Manage VPS servers
• Configure SIP accounts
• Create campaigns
• View call statistics
• Manage phone lists

Need support? Contact @support
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user stats"""
        user = update.effective_user
        db = SessionLocal()
        
        try:
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            
            if not db_user:
                await update.message.reply_text("Please use /start to register first.")
                return
            
            campaigns = db.query(Campaign).filter_by(user_id=db_user.id).all()
            active = sum(1 for c in campaigns if c.status == 'active')
            completed = sum(1 for c in campaigns if c.status == 'completed')
            total_calls = sum(c.total_calls or 0 for c in campaigns)
            
            stats_text = f"""
📊 **Your Statistics**

👤 User: {db_user.first_name}
📅 License Valid: {db_user.license_valid_until.strftime('%Y-%m-%d') if db_user.license_valid_until else 'N/A'}

📞 **Campaigns:**
• Total: {len(campaigns)}
• Active: {active}
• Completed: {completed}

📈 **Calls:**
• Total Calls: {total_calls}

Use the menu below for more options.
"""
            
            await update.message.reply_text(
                stats_text,
                reply_markup=UIBuilder.main_menu(),
                parse_mode='Markdown'
            )
        finally:
            db.close()


if __name__ == '__main__':
    bot = AutoDialerBot()
    bot.run()
