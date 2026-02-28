import asyncio
import logging
from typing import Dict, Optional, Callable
from datetime import datetime
from asterisk.ami import AMIClient, SimpleAction
from gtts import gTTS
import os
import threading
import time
from queue import Queue

logger = logging.getLogger(__name__)

class CampaignManager:
    """Manage campaign execution and call processing"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.active_campaigns = {}  # campaign_id: CampaignRunner
        self.telegram_callback = None
    
    def set_telegram_callback(self, callback: Callable):
        """Set callback for sending Telegram messages"""
        self.telegram_callback = callback
    
    async def start_campaign(self, campaign_id: int, vps_config: Dict) -> bool:
        """Start a campaign"""
        try:
            from database import Campaign, PhoneNumber
            
            campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
            if not campaign:
                return False
            
            # Get phone numbers
            phone_numbers = self.db.query(PhoneNumber).filter_by(
                campaign_id=campaign_id,
                status='pending'
            ).all()
            
            if not phone_numbers:
                logger.warning(f"No pending numbers for campaign {campaign_id}")
                return False
            
            # TTS audio is already generated during campaign creation
            
            # Create campaign runner
            runner = CampaignRunner(
                campaign=campaign,
                phone_numbers=phone_numbers,
                vps_config=vps_config,
                db_session=self.db,
                telegram_callback=self.telegram_callback
            )
            
            # Start runner in background
            self.active_campaigns[campaign_id] = runner
            threading.Thread(target=runner.run, daemon=True).start()
            
            # Update status
            campaign.status = 'running'
            campaign.started_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Campaign {campaign_id} started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start campaign {campaign_id}: {e}")
            return False
    
    async def pause_campaign(self, campaign_id: int) -> bool:
        """Pause a campaign"""
        try:
            runner = self.active_campaigns.get(campaign_id)
            if runner:
                runner.pause()
            
            from database import Campaign
            campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
            if campaign:
                campaign.status = 'paused'
                self.db.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to pause campaign {campaign_id}: {e}")
            return False
    
    async def resume_campaign(self, campaign_id: int) -> bool:
        """Resume a paused campaign"""
        try:
            runner = self.active_campaigns.get(campaign_id)
            if runner:
                runner.resume()
            
            from database import Campaign
            campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
            if campaign:
                campaign.status = 'running'
                self.db.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to resume campaign {campaign_id}: {e}")
            return False
    
    async def stop_campaign(self, campaign_id: int) -> bool:
        """Stop a campaign"""
        try:
            runner = self.active_campaigns.get(campaign_id)
            if runner:
                runner.stop()
                del self.active_campaigns[campaign_id]
            
            from database import Campaign
            campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
            if campaign:
                campaign.status = 'stopped'
                campaign.completed_at = datetime.utcnow()
                self.db.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to stop campaign {campaign_id}: {e}")
            return False
    
    async def get_campaign_stats(self, campaign_id: int) -> Dict:
        """Get campaign statistics"""
        try:
            from database import Campaign, PhoneNumber, CallLog
            
            campaign = self.db.query(Campaign).filter_by(id=campaign_id).first()
            if not campaign:
                return {}
            
            total = self.db.query(PhoneNumber).filter_by(campaign_id=campaign_id).count()
            pending = self.db.query(PhoneNumber).filter_by(campaign_id=campaign_id, status='pending').count()
            calling = self.db.query(PhoneNumber).filter_by(campaign_id=campaign_id, status='calling').count()
            completed = self.db.query(PhoneNumber).filter_by(campaign_id=campaign_id, status='completed').count()
            no_answer = self.db.query(PhoneNumber).filter_by(campaign_id=campaign_id, status='no_answer').count()
            failed = self.db.query(PhoneNumber).filter_by(campaign_id=campaign_id, status='failed').count()
            
            # Get active count from runner
            active = 0
            runner = self.active_campaigns.get(campaign_id)
            if runner:
                active = len(runner.active_calls)
            
            # Total attempted = everyone who got dialed (not still pending)
            attempted = total - pending
            
            # Call logs - count pressed_1 as callbacks (requesting callback)
            callbacks = self.db.query(CallLog).filter_by(campaign_id=campaign_id, status='pressed_1').count()
            
            # Progress based on attempted, success rate based on callbacks vs attempted
            progress_pct = (attempted / total * 100) if total > 0 else 0
            success_rate = (callbacks / attempted * 100) if attempted > 0 else 0
            
            return {
                'total': total,
                'attempted': attempted,
                'pending': pending,
                'calling': calling,
                'completed': completed,
                'no_answer': no_answer,
                'failed': failed,
                'active': active,
                'callbacks': callbacks,
                'progress_pct': progress_pct,
                'success_rate': success_rate
            }
        except Exception as e:
            logger.error(f"Failed to get stats for campaign {campaign_id}: {e}")
            return {}
    
    async def _generate_tts(self, campaign):
        """Generate TTS audio for campaign"""
        try:
            audio_dir = 'audio'
            os.makedirs(audio_dir, exist_ok=True)
            
            filename = f"{audio_dir}/campaign_{campaign.id}_tts.mp3"
            
            tts = gTTS(text=campaign.tts_message, lang='en', slow=False)
            tts.save(filename)
            
            logger.info(f"TTS generated for campaign {campaign.id}")
            return filename
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None


class CampaignRunner:
    """Run a campaign in background"""
    
    def __init__(self, campaign, phone_numbers, vps_config, db_session, telegram_callback):
        self.campaign = campaign
        self.phone_numbers = phone_numbers
        self.vps_config = vps_config
        self.db = None  # Each thread will create its own session
        self.telegram_callback = telegram_callback
        
        self.running = True
        self.paused = False
        self.active_calls = {}
        self.phone_queue = Queue()
        
        # Add all phone numbers to queue
        for phone in phone_numbers:
            self.phone_queue.put(phone)
        
        # Asterisk connection
        self.ami_client = None
    
    def run(self):
        """Main campaign loop"""
        try:
            # Connect to Asterisk
            self.ami_client = AMIClient(
                address=self.vps_config['host'],
                port=self.vps_config['ami_port']
            )
            self.ami_client.login(
                username=self.vps_config['ami_username'],
                secret=self.vps_config['ami_password']
            )
            
            # Register event listener for UserEvents
            self.ami_client.add_event_listener(self._handle_ami_event)
            
            # Start AMI event listener thread
            event_thread = threading.Thread(target=self._ami_event_loop, daemon=True)
            event_thread.start()
            
            # Start cleanup thread to remove old active calls
            cleanup_thread = threading.Thread(target=self._cleanup_old_calls, daemon=True)
            cleanup_thread.start()
            
            logger.info(f"Campaign {self.campaign.id} connected to Asterisk with event listener")
            
            # Start worker threads - scale with concurrency (1 worker per 5 concurrent, min 5, max 20)
            num_workers = max(5, min(20, self.campaign.max_concurrent // 5))
            workers = []
            for i in range(num_workers):
                t = threading.Thread(target=self._worker, daemon=True)
                t.start()
                workers.append(t)
            logger.info(f"Campaign {self.campaign.id} started {num_workers} workers for {self.campaign.max_concurrent} concurrent calls")
            
            # Wait for completion
            while self.running:
                # Check if there are pending calls OR active calls
                pending_count = 0
                if not self.phone_queue.empty():
                    pending_count = self.phone_queue.qsize()
                
                active_count = len(self.active_calls)
                
                logger.debug(f"Campaign loop: pending={pending_count}, active={active_count}")
                
                if pending_count == 0 and active_count == 0:
                    # Campaign complete
                    logger.info(f"Campaign {self.campaign.id} finishing: no pending or active calls")
                    self._on_complete()
                    break
                
                time.sleep(2)  # Check every 2 seconds
            
            # Cleanup
            if self.ami_client:
                self.ami_client.logoff()
                
        except Exception as e:
            logger.error(f"Campaign {self.campaign.id} error: {e}")
            self._on_error(str(e))
    
    def _ami_event_loop(self):
        """Keep event loop alive - events handled by add_event_listener"""
        logger.info(f"===== AMI EVENT LOOP STARTED FOR CAMPAIGN {self.campaign.id} =====")
        while self.running:
            time.sleep(1)  # Events are handled automatically by add_event_listener
    
    def _cleanup_old_calls(self):
        """Remove calls from active_calls that have been there too long and mark as failed"""
        from database import SessionLocal, CallLog, PhoneNumber
        
        try:
            while self.running:
                current_time = time.time()
                to_remove = []
                
                for call_id, call_info in self.active_calls.items():
                    # Remove calls older than 60 seconds (should be done by then)
                    if current_time - call_info.get('created_at', current_time) > 60:
                        to_remove.append((call_id, call_info))
                
                # Update database for expired calls
                if to_remove:
                    db = SessionLocal()
                    try:
                        for call_id, call_info in to_remove:
                            phone_number = call_info.get('phone')
                            logger.info(f"Removing expired call from active_calls: {call_id}")
                            
                            if phone_number:
                                # Update call log to failed if still in calling status
                                call_log = db.query(CallLog).filter_by(
                                    campaign_id=self.campaign.id,
                                    phone_number=phone_number
                                ).order_by(CallLog.timestamp.desc()).first()
                                
                                if call_log and call_log.status == 'calling':
                                    call_log.status = 'no_answer'
                                    call_log.notes = 'Expired: no AMI event received (possible silent SIP rejection)'
                                    logger.info(f"Marked stuck call as no_answer: {phone_number}")
                                
                                # Update phone status to no_answer if still calling
                                phone = db.query(PhoneNumber).filter_by(
                                    campaign_id=self.campaign.id,
                                    phone_number=phone_number
                                ).first()
                                
                                if phone and phone.status == 'calling':
                                    phone.status = 'no_answer'
                                    logger.info(f"Marked stuck phone as no_answer: {phone_number}")
                            
                            del self.active_calls[call_id]
                        
                        db.commit()
                    except Exception as e:
                        logger.error(f"Failed to update stuck calls: {e}")
                        db.rollback()
                    finally:
                        db.close()
                
                time.sleep(5)  # Check every 5 seconds
        except Exception as e:
            logger.error(f"Cleanup thread error: {e}")
    
    def _handle_ami_event(self, event, **kwargs):
        """Handle AMI events from Asterisk"""
        try:
            event_name = event.name if hasattr(event, 'name') else ''

            # ── OriginateResponse: fires for EVERY async originate (answered OR not) ──
            if event_name == 'OriginateResponse':
                try:
                    import re
                    event_str = str(event)
                    # Channel: PJSIP/14388156539@trunk_majes-00000001
                    channel_match = re.search(r"'Channel': 'PJSIP/(\d+)[@-]", event_str)
                    if not channel_match:
                        return
                    phone_number = channel_match.group(1)
                    is_ours = any(v.get('phone') == phone_number for v in self.active_calls.values())
                    if not is_ours:
                        return
                    response_match = re.search(r"'Response': '([^']*)'", event_str)
                    reason_match = re.search(r"'Reason': '([^']*)'", event_str)
                    response = response_match.group(1) if response_match else ''
                    reason = reason_match.group(1) if reason_match else '0'
                    # Reason 4 = Success/Answered – dialplan already handles it via UserEvent
                    if response == 'Success':
                        logger.info(f"OriginateResponse Success for {phone_number} – dialplan will handle it")
                        return
                    # Failed – map Originate reason to equivalent SIP cause code
                    reason_to_cause = {
                        '0': '1',   # No answer/failed → unallocated
                        '1': '21',  # Cancelled → call rejected
                        '5': '17',  # Busy → user busy
                        '8': '19',  # No answer timeout → no answer
                    }
                    cause_code = reason_to_cause.get(reason, '19')  # default no_answer
                    logger.info(f"📵 OriginateResponse Failure for {phone_number}: reason={reason} → cause {cause_code}")
                    self._update_call_status(phone_number, 'hangup',
                                             hangupcause=cause_code,
                                             hangupcause_txt=f'OriginateFailure reason={reason}')
                except Exception as e:
                    logger.debug(f"OriginateResponse parse error: {e}")
                return

            # ── Native Hangup event (backup for any missed OriginateResponse) ──
            if event_name == 'Hangup':
                try:
                    import re
                    event_str = str(event)

                    # Extract phone number from Channel: PJSIP/15145551234@trunk_majes-00000001
                    channel_match = re.search(r"'Channel': 'PJSIP/(\d+)[@-]", event_str)
                    if not channel_match:
                        return  # Not one of our outbound PJSIP channels

                    phone_number = channel_match.group(1)

                    # Only handle if this phone is in our active_calls
                    is_ours = any(v.get('phone') == phone_number for v in self.active_calls.values())
                    if not is_ours:
                        return

                    cause_match = re.search(r"'Cause': '([^']*)'", event_str)
                    cause_txt_match = re.search(r"'Cause-txt': '([^']*)'", event_str)
                    hangupcause = cause_match.group(1) if cause_match else None
                    hangupcause_txt = cause_txt_match.group(1) if cause_txt_match else None

                    logger.info(f"📵 AMI Hangup for {phone_number}: cause={hangupcause} ({hangupcause_txt})")
                    self._update_call_status(phone_number, 'hangup',
                                             hangupcause=hangupcause,
                                             hangupcause_txt=hangupcause_txt)
                except Exception as e:
                    logger.debug(f"Hangup event parse error: {e}")
                return

            # ── UserEvent (dialplan-sent events for answered/pressed_1/etc.) ──
            if event_name == 'UserEvent':
                logger.info(f"✅ Received UserEvent for campaign {self.campaign.id}")
                
                # Try multiple methods to extract event data
                campaign_id = None
                phone_number = None
                status = None
                
                # Method 1: Try event.keys() as dict
                try:
                    event_dict = event.keys() if hasattr(event, 'keys') else {}
                    if 'UserEvent' in event_dict and event_dict.get('UserEvent') == 'CampaignCall':
                        campaign_id = event_dict.get('CampaignID')
                        phone_number = event_dict.get('PhoneNumber')
                        status = event_dict.get('Status')
                        logger.info(f"Method 1 (keys dict): Campaign={campaign_id}, Phone={phone_number}, Status={status}")
                except Exception as e:
                    logger.debug(f"Method 1 failed: {e}")
                
                # Method 2: Direct event.get() access
                if not all([campaign_id, phone_number, status]):
                    try:
                        user_event = event.get('UserEvent') if hasattr(event, 'get') else None
                        if user_event == 'CampaignCall':
                            campaign_id = event.get('CampaignID')
                            phone_number = event.get('PhoneNumber')
                            status = event.get('Status')
                            logger.info(f"Method 2 (direct get): Campaign={campaign_id}, Phone={phone_number}, Status={status}")
                    except Exception as e:
                        logger.debug(f"Method 2 failed: {e}")
                
                # Method 3: Regex parsing from string representation (MOST RELIABLE)
                if not all([campaign_id, phone_number, status]):
                    try:
                        import re
                        event_str = str(event)
                        logger.debug(f"Event string: {event_str[:200]}")
                        
                        # Parse the event string
                        camp_match = re.search(r"'CampaignID': '(\d+)'", event_str)
                        phone_match = re.search(r"'PhoneNumber': '([^']+)'", event_str)
                        status_match = re.search(r"'Status': '([^']+)'", event_str)
                        
                        if camp_match:
                            campaign_id = camp_match.group(1)
                        if phone_match:
                            phone_number = phone_match.group(1)
                        if status_match:
                            status = status_match.group(1)
                        
                        logger.info(f"Method 3 (regex): Campaign={campaign_id}, Phone={phone_number}, Status={status}")
                    except Exception as e:
                        logger.error(f"Method 3 failed: {e}")
                
                # Extract cause code from hangup events (new field in dialplan)
                hangupcause = None
                hangupcause_txt = None
                if status == 'hangup':
                    try:
                        import re
                        event_str = str(event)
                        cause_match = re.search(r"'Cause': '([^']*)'" , event_str)
                        cause_txt_match = re.search(r"'CauseTxt': '([^']*)'" , event_str)
                        if cause_match:
                            hangupcause = cause_match.group(1)
                        if cause_txt_match:
                            hangupcause_txt = cause_txt_match.group(1)
                        if hangupcause:
                            logger.info(f"HangupCause for {phone_number}: {hangupcause} ({hangupcause_txt})")
                    except Exception as e:
                        logger.debug(f"Cause extraction failed: {e}")
                
                # Process if we got valid data
                if campaign_id and int(campaign_id) == self.campaign.id:
                    logger.info(f"✅ Campaign {campaign_id} event: {status} for {phone_number}")
                    self._update_call_status(phone_number, status, hangupcause=hangupcause, hangupcause_txt=hangupcause_txt)
                else:
                    logger.debug(f"Event for different campaign: {campaign_id} vs {self.campaign.id}")
                    
        except Exception as e:
            logger.error(f"Error handling AMI event: {e}", exc_info=True)
    
    def _resolve_status_from_cause(self, cause):
        """Map Asterisk HANGUPCAUSE code to phone status."""
        if cause is None:
            return 'no_answer'
        try:
            cause = int(cause)
        except (ValueError, TypeError):
            return 'no_answer'
        # Truly bad / unreachable numbers → failed
        if cause in [1, 20, 27, 28, 38, 2, 3, 88]:
            return 'failed'
        # Busy signal
        if cause == 17:
            return 'busy'
        # Everything else (16=normal, 17=busy, 18/19=noanswer, 21=cancel, 34=congestion…)
        return 'no_answer'

    def _cause_note(self, cause, cause_txt):
        """Build a human-readable note string for a hangup cause."""
        cause_map = {
            1: 'Unallocated/invalid number',
            2: 'No route to transit network',
            3: 'No route to destination',
            16: 'Normal call clearing',
            17: 'User busy',
            18: 'No user responding (timeout)',
            19: 'No answer from user (alerting)',
            20: 'Subscriber absent',
            21: 'Call rejected / CANCEL',
            27: 'Destination out of order',
            28: 'Invalid number format',
            34: 'Circuit/channel congestion',
            38: 'Network out of order',
            88: 'Incompatible destination',
        }
        code = None
        try:
            code = int(cause)
        except (TypeError, ValueError):
            pass
        if code is not None:
            desc = cause_map.get(code, cause_txt or 'Unknown')
            return f"Cause {code}: {desc}"
        return f"Cause: {cause_txt or 'Unknown'}"

    def _update_call_status(self, phone_number, status, hangupcause=None, hangupcause_txt=None):
        """Update call status in database"""
        from database import SessionLocal, CallLog, PhoneNumber
        db = SessionLocal()
        try:
            # Find the most recent call log for this number
            call_log = db.query(CallLog).filter_by(
                campaign_id=self.campaign.id,
                phone_number=phone_number
            ).order_by(CallLog.timestamp.desc()).first()
            
            if call_log:
                # Don't overwrite completed statuses (transferred/callback/pressed_1) with hangup
                if call_log.status not in ["transferred", "callback", "pressed_1"] or status in ["transferred", "callback", "pressed_1"]:
                    call_log.status = status
                    # Update action_taken field for pressed_1
                    if status == 'pressed_1':
                        call_log.action_taken = 'pressed_1'
                    # Store hangup cause in notes
                    if status == 'hangup' and hangupcause:
                        call_log.notes = self._cause_note(hangupcause, hangupcause_txt)
                    logger.info(f"Updated call log status: {phone_number} -> {status} (cause={hangupcause})")
                else:
                    logger.info(f"Keeping existing status {call_log.status}, not overwriting with {status}")
                
                # Update phone number status
                phone = db.query(PhoneNumber).filter_by(
                    campaign_id=self.campaign.id,
                    phone_number=phone_number
                ).first()
                
                if phone:
                    # Only update if not already completed
                    if phone.status != 'completed' or status in ['transferred', 'callback', 'pressed_1']:
                        if status in ['transferred', 'callback', 'pressed_1']:
                            phone.status = 'completed'
                        elif status == 'answered':
                            phone.status = 'calling'
                        elif status == 'no_response' and phone.status != 'completed':
                            phone.status = 'no_answer'
                        elif status == 'hangup' and phone.status not in ['completed', 'no_answer', 'busy', 'failed']:
                            # Map cause code to the most accurate status
                            phone.status = self._resolve_status_from_cause(hangupcause)
                        logger.info(f"Updated phone status: {phone_number} -> {phone.status}")
                
                db.commit()
                
                # Remove from active calls if call is done
                if status in ['transferred', 'callback', 'pressed_1', 'hangup', 'no_response']:
                    for call_id, call_info in list(self.active_calls.items()):
                        if call_info.get('phone') == phone_number:
                            logger.info(f"Removing completed call from active: {call_id}")
                            del self.active_calls[call_id]
                            break
                
                # Send telegram notification (use telegram_id, not user_id!)
                if self.telegram_callback and status in ['transferred', 'callback', 'pressed_1']:
                    try:
                        import threading
                        def send_notification():
                            try:
                                import asyncio
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                
                                telegram_id = self.campaign.user.telegram_id
                                
                                # Create user-friendly status message
                                if status == 'pressed_1':
                                    status_msg = "PRESSED 1 (Callback Request)"
                                elif status == 'transferred':
                                    status_msg = "TRANSFERRED"
                                elif status == 'callback':
                                    status_msg = "CALLBACK REQUEST"
                                else:
                                    status_msg = status.upper()
                                
                                message = f"📞 **Campaign Update**\n\nPhone: {phone_number}\nStatus: {status_msg}\nCampaign: {self.campaign.name}"
                                
                                loop.run_until_complete(self.telegram_callback(telegram_id, message))
                                loop.close()
                                logger.info(f"✅ Sent {status} notification to {telegram_id}")
                            except Exception as e:
                                logger.error(f"Failed to send notification: {e}")
                        threading.Thread(target=send_notification, daemon=True).start()
                    except Exception as e:
                        logger.error(f"Error setting up notification: {e}")
            else:
                logger.warning(f"No CallLog found for {phone_number} to update status")
        except Exception as e:
            logger.error(f"Error updating call status: {e}")
        finally:
            db.close()
    
    def _worker(self):
        """Worker thread to process calls"""
        from database import SessionLocal
        # Create thread-local database session
        db = SessionLocal()
        
        try:
            while self.running:
                if self.paused:
                    time.sleep(1)
                    continue
                
                # Check concurrent limit
                if len(self.active_calls) >= self.campaign.max_concurrent:
                    time.sleep(1)
                    continue
                
                # Get next phone number
                if not self.phone_queue.empty():
                    phone = self.phone_queue.get()
                    self._make_call(phone, db)
                    time.sleep(0.3)  # Stagger calls to avoid SIP provider burst rejection
                else:
                    time.sleep(1)
        finally:
            db.close()
    
    def _make_call(self, phone, db):
        """Make a call to a phone number"""
        try:
            from database import CallLog, VPSServer, SIPAccount, PhoneNumber as PhoneNum
            
            call_id = f"{phone.phone_number}_{int(time.time())}"
            self.active_calls[call_id] = {
                'phone': phone.phone_number,
                'start_time': time.time(),
                'status': 'calling',
                'created_at': time.time()
            }
            
            # Re-query phone using local session to avoid cross-session issues
            phone_obj = db.query(PhoneNum).filter_by(
                campaign_id=self.campaign.id,
                phone_number=phone.phone_number
            ).first()
            if not phone_obj:
                logger.error(f"Phone {phone.phone_number} not found in local session")
                del self.active_calls[call_id]
                return
            
            # Get VPS server info for SIP trunk name
            server = db.query(VPSServer).filter_by(id=self.campaign.server_id).first()
            # Get SIP account name
            sip_account = db.query(SIPAccount).filter_by(id=self.campaign.sip_account_id).first()
            trunk_name = sip_account.name if sip_account else "trunk_majes"
            
            # Format phone number - keep the number as-is, just remove special characters
            phone_number = phone.phone_number.replace('+', '').replace('-', '').replace(' ', '')
            # Don't strip the leading 1 - SIP trunk needs it for North American numbers
            
            logger.info(f"Dialing phone: {phone_number}, trunk: {trunk_name}")
            
            # Set caller ID
            caller_id_name = server.caller_id_name if server and server.caller_id_name else "AutoDialer"
            caller_id_num = server.caller_id_number if server and server.caller_id_number else phone_number
            
            # Originate call via Asterisk using campaign context
            channel_str = f'PJSIP/{phone_number}@{trunk_name}'
            logger.info(f"AMI Channel parameter: {channel_str}")
            
            action = SimpleAction(
                'Originate',
                Channel=channel_str,
                Context=f'campaign-{self.campaign.id}',
                Exten='s',
                Priority='1',
                CallerID=f'{caller_id_name} <{caller_id_num}>',
                Timeout='30000',
                Async='true',
                Variable=f'CAMPAIGN_ID={self.campaign.id},PHONE_NUMBER={phone.phone_number},TRANSFER_NUMBER={self.campaign.transfer_number},SIP_TRUNK={trunk_name}'
            )
            
            response = self.ami_client.send_action(action)
            
            # AMI response is an object, convert to string and check for errors
            response_str = str(response) if response else 'No response'
            logger.info(f"AMI Originate response for {phone.phone_number}: {response_str}")
            
            # Check if call initiation failed
            if 'Error' in response_str or 'Failed' in response_str:
                logger.error(f"AMI Originate failed: {response_str}")
                raise Exception(f"Call initiation failed: {response_str}")
            
            # Call was initiated successfully - create call log immediately
            logger.info(f"Creating CallLog for {phone_obj.phone_number}")
            call_log = CallLog(
                campaign_id=self.campaign.id,
                phone_number=phone_obj.phone_number,
                status='calling'
            )
            db.add(call_log)
            
            # Update phone number status using local session object
            phone_obj.status = 'calling'
            phone_obj.attempts += 1
            phone_obj.last_attempt = datetime.utcnow()
            db.commit()
            
            # Keep call in active_calls for at least 30 seconds (typical call duration)
            self.active_calls[call_id]['created_at'] = time.time()
            
            logger.info(f"Call initiated to {phone.phone_number} via {trunk_name}, call_id: {call_id}")
            
        except Exception as e:
            logger.error(f"Failed to make call to {phone.phone_number}: {e}", exc_info=True)
            try:
                if call_id in self.active_calls:
                    del self.active_calls[call_id]
                from database import PhoneNumber as PhoneNum
                phone_fail = db.query(PhoneNum).filter_by(
                    campaign_id=self.campaign.id,
                    phone_number=phone.phone_number
                ).first()
                if phone_fail:
                    phone_fail.status = 'failed'
                    db.commit()
            except:
                pass
    
    def pause(self):
        """Pause campaign"""
        self.paused = True
        logger.info(f"Campaign {self.campaign.id} paused")
    
    def resume(self):
        """Resume campaign"""
        self.paused = False
        logger.info(f"Campaign {self.campaign.id} resumed")
    
    def stop(self):
        """Stop campaign"""
        self.running = False
        logger.info(f"Campaign {self.campaign.id} stopped")
    
    def _on_complete(self):
        """Handle campaign completion"""
        logger.info(f"Campaign {self.campaign.id} completed")
        
        try:
            from database import SessionLocal, Campaign, PhoneNumber, CallLog
            db = SessionLocal()
            try:
                # Mark any phones/logs still stuck as 'calling' → 'no_answer'
                stuck_phones = db.query(PhoneNumber).filter_by(
                    campaign_id=self.campaign.id,
                    status='calling'
                ).all()
                for p in stuck_phones:
                    p.status = 'no_answer'
                    logger.info(f"Marking stuck phone as no_answer: {p.phone_number}")
                
                stuck_logs = db.query(CallLog).filter_by(
                    campaign_id=self.campaign.id,
                    status='calling'
                ).all()
                for log in stuck_logs:
                    log.status = 'no_answer'
                
                campaign = db.query(Campaign).filter_by(id=self.campaign.id).first()
                if campaign:
                    campaign.status = 'completed'
                    campaign.completed_at = datetime.utcnow()
                
                db.commit()
                
                attempted = db.query(PhoneNumber).filter(
                    PhoneNumber.campaign_id == self.campaign.id,
                    PhoneNumber.status != 'pending'
                ).count()
                callbacks = db.query(CallLog).filter_by(
                    campaign_id=self.campaign.id,
                    status='pressed_1'
                ).count()
                total = len(self.phone_numbers)
                
                logger.info(f"Campaign {self.campaign.id} completed: {attempted} dialed, {callbacks} pressed 1, out of {total} total")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Campaign complete error: {e}")
    
    def _on_error(self, error_message):
        """Handle campaign error"""
        logger.error(f"Campaign {self.campaign.id} error: {error_message}")
        
        try:
            from database import SessionLocal, Campaign
            db = SessionLocal()
            try:
                campaign = db.query(Campaign).filter_by(id=self.campaign.id).first()
                if campaign:
                    campaign.status = 'stopped'
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Campaign error handler failed: {e}")
