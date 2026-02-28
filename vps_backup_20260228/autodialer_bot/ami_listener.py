"""
AMI Event Listener
Monitors Asterisk Manager Interface events and triggers actions
"""
import asyncio
import logging
from typing import Callable, Dict, Optional
from datetime import datetime
from panoramisk import Manager
import re

logger = logging.getLogger(__name__)


class AMIListener:
    """Listen for AMI events from Asterisk"""
    
    def __init__(self, host: str, port: int, username: str, secret: str):
        """
        Initialize AMI listener
        
        Args:
            host: Asterisk host
            port: AMI port (usually 5038)
            username: AMI username
            secret: AMI password
        """
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self.manager = None
        self.running = False
        
        # Event callbacks
        self.on_campaign_action = None
        self.on_campaign_end = None
        self.on_call_answered = None
        self.on_call_failed = None
    
    async def connect(self) -> bool:
        """Connect to AMI"""
        try:
            self.manager = Manager(
                host=self.host,
                port=self.port,
                username=self.username,
                secret=self.secret,
                ping_delay=10,
                ping_tries=3
            )
            
            # Register event handlers
            self.manager.register_event('UserEvent', self._handle_user_event)
            self.manager.register_event('Hangup', self._handle_hangup)
            self.manager.register_event('DialBegin', self._handle_dial_begin)
            self.manager.register_event('DialEnd', self._handle_dial_end)
            
            await self.manager.connect()
            logger.info(f"Connected to AMI at {self.host}:{self.port}")
            self.running = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to AMI: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from AMI"""
        if self.manager:
            try:
                await self.manager.close()
                logger.info("Disconnected from AMI")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
        
        self.running = False
    
    async def _handle_user_event(self, manager, event):
        """Handle UserEvent from dialplan"""
        try:
            user_event_name = event.get('UserEvent', '')
            
            if user_event_name == 'CampaignAction':
                # Parse campaign action event
                campaign_id = event.get('Campaign', '')
                phone_number = event.get('Phone', '')
                action = event.get('Action', '')
                
                logger.info(f"Campaign {campaign_id}: {phone_number} -> {action}")
                
                # Trigger callback
                if self.on_campaign_action:
                    await self.on_campaign_action({
                        'campaign_id': int(campaign_id) if campaign_id.isdigit() else campaign_id,
                        'phone_number': phone_number,
                        'action': action,
                        'timestamp': event.get('Timestamp', '')
                    })
            
            elif user_event_name == 'CampaignEnd':
                # Parse campaign end event
                campaign_id = event.get('Campaign', '')
                phone_number = event.get('Phone', '')
                duration = event.get('Duration', '0')
                status = event.get('Status', '')
                
                logger.info(f"Campaign {campaign_id}: Call to {phone_number} ended ({duration}s)")
                
                # Trigger callback
                if self.on_campaign_end:
                    await self.on_campaign_end({
                        'campaign_id': int(campaign_id) if campaign_id.isdigit() else campaign_id,
                        'phone_number': phone_number,
                        'duration': int(duration) if duration.isdigit() else 0,
                        'status': status
                    })
        
        except Exception as e:
            logger.error(f"Error handling UserEvent: {e}")
    
    async def _handle_hangup(self, manager, event):
        """Handle Hangup event"""
        try:
            channel = event.get('Channel', '')
            cause = event.get('Cause', '')
            cause_txt = event.get('Cause-txt', '')
            
            logger.debug(f"Hangup: {channel} - {cause_txt}")
            
        except Exception as e:
            logger.error(f"Error handling Hangup: {e}")
    
    async def _handle_dial_begin(self, manager, event):
        """Handle DialBegin event"""
        try:
            dest_channel = event.get('DestChannel', '')
            caller_id = event.get('CallerIDNum', '')
            
            logger.debug(f"Dial begin: {caller_id} -> {dest_channel}")
            
            if self.on_call_answered:
                await self.on_call_answered({
                    'channel': dest_channel,
                    'caller_id': caller_id
                })
        
        except Exception as e:
            logger.error(f"Error handling DialBegin: {e}")
    
    async def _handle_dial_end(self, manager, event):
        """Handle DialEnd event"""
        try:
            dial_status = event.get('DialStatus', '')
            dest_channel = event.get('DestChannel', '')
            
            logger.debug(f"Dial end: {dest_channel} - {dial_status}")
            
            # Check for failed calls
            if dial_status in ['BUSY', 'NOANSWER', 'CONGESTION', 'CHANUNAVAIL']:
                if self.on_call_failed:
                    await self.on_call_failed({
                        'channel': dest_channel,
                        'status': dial_status
                    })
        
        except Exception as e:
            logger.error(f"Error handling DialEnd: {e}")
    
    async def send_command(self, action: str, **kwargs) -> Dict:
        """
        Send AMI command
        
        Args:
            action: AMI action name
            **kwargs: Action parameters
        
        Returns:
            Response dict
        """
        try:
            if not self.manager:
                return {'success': False, 'error': 'Not connected'}
            
            response = await self.manager.send_action({
                'Action': action,
                **kwargs
            })
            
            return {
                'success': response.success,
                'response': response.as_list() if hasattr(response, 'as_list') else str(response)
            }
            
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def originate_call(self, channel: str, context: str, extension: str = 's',
                           caller_id: str = None, variables: Dict = None) -> Dict:
        """
        Originate an outbound call via AMI
        
        Args:
            channel: Channel to dial (e.g., PJSIP/1234567890@trunk)
            context: Dialplan context
            extension: Extension in context (default: s)
            caller_id: Caller ID to present
            variables: Channel variables
        
        Returns:
            Result dict
        """
        try:
            params = {
                'Channel': channel,
                'Context': context,
                'Exten': extension,
                'Priority': '1',
                'Async': 'true'
            }
            
            if caller_id:
                params['CallerID'] = caller_id
            
            if variables:
                var_str = ','.join([f'{k}={v}' for k, v in variables.items()])
                params['Variable'] = var_str
            
            return await self.send_command('Originate', **params)
            
        except Exception as e:
            logger.error(f"Originate failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_active_channels(self) -> Dict:
        """Get active channels count"""
        try:
            result = await self.send_command('CoreShowChannels')
            
            if result['success']:
                # Parse response for channel count
                count = 0
                response_text = str(result.get('response', ''))
                
                # Look for channel count in response
                match = re.search(r'(\d+)\s+active\s+channel', response_text, re.IGNORECASE)
                if match:
                    count = int(match.group(1))
                
                return {
                    'success': True,
                    'count': count
                }
            else:
                return {'success': False, 'error': 'Command failed'}
        
        except Exception as e:
            logger.error(f"Failed to get channels: {e}")
            return {'success': False, 'error': str(e)}
    
    async def hangup_channel(self, channel: str) -> Dict:
        """Hangup a specific channel"""
        try:
            return await self.send_command('Hangup', Channel=channel)
        except Exception as e:
            logger.error(f"Hangup failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def reload_dialplan(self) -> Dict:
        """Reload dialplan"""
        try:
            return await self.send_command('Command', Command='dialplan reload')
        except Exception as e:
            logger.error(f"Reload failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def run(self):
        """Run the event listener loop"""
        try:
            if not await self.connect():
                logger.error("Failed to connect to AMI")
                return
            
            logger.info("AMI listener running...")
            
            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"AMI listener error: {e}")
        finally:
            await self.disconnect()


class AMIEventHandler:
    """
    High-level AMI event handler for campaigns
    Integrates with database and Telegram bot
    """
    
    def __init__(self, ami_listener: AMIListener, database, telegram_bot):
        """
        Initialize event handler
        
        Args:
            ami_listener: AMIListener instance
            database: Database module
            telegram_bot: Telegram bot instance
        """
        self.ami = ami_listener
        self.db = database
        self.bot = telegram_bot
        
        # Register callbacks
        self.ami.on_campaign_action = self.handle_campaign_action
        self.ami.on_campaign_end = self.handle_campaign_end
    
    async def handle_campaign_action(self, event: Dict):
        """
        Handle campaign action (press 1) - SIMPLIFIED NOTIFICATION ONLY
        
        Args:
            event: Event data from AMI
        """
        try:
            campaign_id = event['campaign_id']
            phone_number = event['phone_number']
            action = event['action']
            
            logger.info(f"Action: {action} - Campaign {campaign_id} - {phone_number}")
            
            # Update database
            from database import CallLog, Campaign
            
            # Find or create call log
            call_log = self.db.query(CallLog).filter_by(
                campaign_id=campaign_id,
                phone_number=phone_number
            ).first()
            
            if call_log:
                call_log.action_taken = action
                call_log.answered = True
                self.db.commit()
            
            # Update campaign stats and send notification
            campaign = self.db.query(Campaign).get(campaign_id)
            if campaign:
                if action == 'pressed_1' or action == 'transferred':
                    campaign.transferred_calls += 1
                    
                    # Send simple notification that someone pressed 1
                    await self._send_press_1_notification(campaign, phone_number)
                    
                elif action == 'no_response':
                    campaign.no_answer_calls += 1
                
                elif action == 'transfer_failed' or action == 'missed_transfer':
                    campaign.failed_calls += 1
                
                self.db.commit()
        
        except Exception as e:
            logger.error(f"Error handling campaign action: {e}")
    
    async def handle_campaign_end(self, event: Dict):
        """Handle campaign call end"""
        try:
            campaign_id = event['campaign_id']
            phone_number = event['phone_number']
            duration = event['duration']
            
            logger.info(f"Call ended: Campaign {campaign_id} - {phone_number} - {duration}s")
            
            # Update call log with duration
            from database import CallLog
            
            call_log = self.db.query(CallLog).filter_by(
                campaign_id=campaign_id,
                phone_number=phone_number
            ).first()
            
            if call_log:
                call_log.duration = duration
                self.db.commit()
        
        except Exception as e:
            logger.error(f"Error handling campaign end: {e}")
    
async def _send_press_1_notification(self, campaign, phone_number: str):
        """Send simple Telegram notification when someone presses 1"""
        try:
            message = (
                f"📞 **Phone number {phone_number} pressed 1**\n\n"
                f"Campaign: {campaign.name}\n"
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Send to campaign owner
            await self.bot.send_message(
                chat_id=campaign.user.telegram_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Press 1 notification sent for {phone_number}")
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
