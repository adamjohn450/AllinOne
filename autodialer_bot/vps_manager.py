import paramiko
import logging
from typing import Optional, Dict, Callable
import time
import os
import secrets
import string
from pathlib import Path
from asterisk_config import AsteriskConfig

logger = logging.getLogger(__name__)

class VPSManager:
    """Manage VPS connections and Asterisk installation"""
    
    def __init__(self, host: str, username: str, password: str = None, key_path: str = None, port: int = 22):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        self.client = None
        self.last_error = None
    
    def connect(self) -> bool:
        """Connect to VPS via SSH"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.key_path:
                self.client.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    key_filename=self.key_path,
                    timeout=10
                )
            else:
                self.client.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10
                )
            
            logger.info(f"Connected to VPS: {self.host}")
            self.last_error = None
            return True
        except paramiko.AuthenticationException as e:
            self.last_error = f"Authentication failed - check username/password"
            logger.error(f"Authentication failed for {self.host}: {e}")
            return False
        except paramiko.SSHException as e:
            self.last_error = f"SSH error: {str(e)}"
            logger.error(f"SSH error for {self.host}: {e}")
            return False
        except Exception as e:
            self.last_error = f"Connection error: {str(e)}"
            logger.error(f"Failed to connect to VPS {self.host}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from VPS"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from VPS")
    
    def execute_command(self, command: str, sudo: bool = False) -> Dict:
        """Execute command on VPS"""
        try:
            if sudo and not command.startswith('sudo'):
                command = f"sudo {command}"
            
            stdin, stdout, stderr = self.client.exec_command(command)
            
            # Wait for command to complete
            exit_status = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            return {
                'success': exit_status == 0,
                'output': output,
                'error': error,
                'exit_code': exit_status
            }
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'exit_code': -1
            }
    
    def check_asterisk_installed(self) -> bool:
        """Check if Asterisk is already installed"""
        result = self.execute_command('which asterisk')
        return result['success'] and '/asterisk' in result['output']
    
    def generate_random_password(self, length: int = 16) -> str:
        """Generate a secure random password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password
    
    def detect_os(self) -> str:
        """Detect operating system"""
        result = self.execute_command('cat /etc/os-release')
        if result['success']:
            output = result['output'].lower()
            if 'ubuntu' in output:
                return 'ubuntu'
            elif 'debian' in output:
                return 'debian'
            elif 'centos' in output:
                return 'centos'
            elif 'rhel' in output:
                return 'rhel'
        return 'unknown'
    
    def install_asterisk(self, progress_callback=None) -> bool:
        """Install and configure Asterisk"""
        try:
            if progress_callback:
                progress_callback("🔍 Detecting OS...")
            
            os_type = self.detect_os()
            if os_type == 'unknown':
                logger.error("Unknown OS type")
                return False
            
            # Check if already installed
            if self.check_asterisk_installed():
                if progress_callback:
                    progress_callback("✅ Asterisk already installed!")
                    progress_callback("⚙️ Now configuring Asterisk for auto-dialing...")
                    progress_callback("This will set up AMI, dialplan, and other configs.")
                config_result = self.configure_asterisk(progress_callback)
                if config_result.get('success'):
                    if progress_callback:
                        progress_callback(f"✅ Asterisk configured successfully!")
                        progress_callback(f"")
                        progress_callback(f"Your VPS is ready to make calls!")
                        progress_callback(f"")
                        progress_callback(f"AMI Credentials:")
                        progress_callback(f"• Username: {config_result['ami_username']}")
                        progress_callback(f"• Password: {config_result['ami_password']}")
                        progress_callback(f"")
                        progress_callback(f"These have been saved securely.")
                    return config_result  # Return dict with credentials
                return False
            
            if progress_callback:
                progress_callback(f"📦 Installing on {os_type.title()}...")
            
            # Upload install script
            install_script = self._generate_install_script(os_type)
            script_path = '/tmp/install_asterisk.sh'
            
            # Write script to VPS
            sftp = self.client.open_sftp()
            with sftp.file(script_path, 'w') as f:
                f.write(install_script)
            sftp.close()
            
            if progress_callback:
                progress_callback("🔧 Running installation (this may take 15-30 minutes)...")
            
            # Make executable and run
            self.execute_command(f'chmod +x {script_path}')
            result = self.execute_command(f'bash {script_path} 2>&1', sudo=True)
            
            if result['success']:
                if progress_callback:
                    progress_callback("✅ Asterisk installed successfully!")
                return True
            else:
                error_msg = result.get('error', '') or result.get('output', '')
                # Get last 5 lines of error for debugging
                error_lines = error_msg.strip().split('\n')[-5:]
                detailed_error = '\n'.join(error_lines)
                logger.error(f"Asterisk installation failed. Last output:\n{detailed_error}")
                if progress_callback:
                    progress_callback(f"❌ Installation failed: {detailed_error}")
                return False
                
        except Exception as e:
            logger.error(f"Asterisk installation failed: {e}")
            if progress_callback:
                progress_callback(f"❌ Error: {str(e)}")
            return False
    
    def configure_asterisk(self, progress_callback: Optional[Callable] = None, 
                          ami_username: str = 'autodialer', 
                          ami_password: str = None) -> Dict:
        """
        Configure Asterisk for autodialer with proper configs
        
        Returns:
            Dict with ami_username, ami_password, and success status
        """
        try:
            if progress_callback:
                progress_callback("⚙️ Configuring Asterisk...")
            
            # Generate configurations using AsteriskConfig
            ami_config = AsteriskConfig.generate_ami_config(ami_username, ami_password)
            dialplan_config = AsteriskConfig.generate_dialplan()
            modules_config = AsteriskConfig.generate_modules_config()
            rtp_config = AsteriskConfig.generate_rtp_config()
            logger_config = AsteriskConfig.generate_logger_config()
            cdr_config = AsteriskConfig.generate_cdr_config()
            moh_config = AsteriskConfig.generate_musiconhold_config()
            
            # Extract password if generated
            if not ami_password:
                for line in ami_config.split('\n'):
                    if 'secret =' in line:
                        ami_password = line.split('=')[1].strip()
                        break
            
            configs = {
                '/etc/asterisk/manager.conf': ami_config,
                '/etc/asterisk/extensions.conf': dialplan_config,
                '/etc/asterisk/modules.conf': modules_config,
                '/etc/asterisk/rtp.conf': rtp_config,
                '/etc/asterisk/logger.conf': logger_config,
                '/etc/asterisk/cdr.conf': cdr_config,
                '/etc/asterisk/musiconhold.conf': moh_config
            }
            
            # Write configs using sudo
            for config_path, content in configs.items():
                if progress_callback:
                    progress_callback(f"📝 Writing {config_path}...")
                
                # Write to temp file first
                temp_path = f'/tmp/{os.path.basename(config_path)}'
                sftp = self.client.open_sftp()
                with sftp.file(temp_path, 'w') as f:
                    f.write(content)
                sftp.close()
                
                # Move with sudo
                result = self.execute_command(f'mv {temp_path} {config_path}', sudo=True)
                if not result['success']:
                    logger.warning(f"Failed to write {config_path}: {result['error']}")
            
            # Set permissions
            self.execute_command('chown -R asterisk:asterisk /etc/asterisk', sudo=True)
            self.execute_command('chmod 640 /etc/asterisk/*.conf', sudo=True)
            
            # Restart Asterisk
            if progress_callback:
                progress_callback("🔄 Restarting Asterisk...")
            
            self.execute_command('systemctl restart asterisk', sudo=True)
            time.sleep(5)
            
            # Verify it's running
            result = self.execute_command('systemctl is-active asterisk', sudo=True)
            if 'active' in result['output']:
                if progress_callback:
                    progress_callback("✅ Asterisk configured and running!")
                
                return {
                    'success': True,
                    'ami_username': ami_username,
                    'ami_password': ami_password,
                    'ami_port': 5038
                }
            else:
                if progress_callback:
                    progress_callback("⚠️ Asterisk may not be running correctly")
                
                # Get error details
                status_result = self.execute_command('systemctl status asterisk', sudo=True)
                logger.error(f"Asterisk status: {status_result['output']}")
                
                return {
                    'success': False,
                    'error': 'Asterisk not active after restart'
                }
                
        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            if progress_callback:
                progress_callback(f"❌ Configuration error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_install_script(self, os_type: str) -> str:
        """Generate Asterisk installation script using AsteriskConfig"""
        return AsteriskConfig.generate_install_script(os_type)
    
    def test_ami_connection(self, ami_username: str, ami_password: str, ami_port: int = 5038) -> bool:
        """Test AMI connection"""
        try:
            from asterisk.ami import AMIClient
            
            client = AMIClient(host=self.host, port=ami_port)
            client.login(username=ami_username, secret=ami_password)
            client.logoff()
            
            logger.info("AMI connection test successful")
            return True
        except Exception as e:
            logger.error(f"AMI connection test failed: {e}")
            return False
    
    def get_asterisk_status(self) -> Dict:
        """Get Asterisk status information"""
        try:
            # Check if service is running
            result = self.execute_command('systemctl status asterisk', sudo=True)
            is_running = 'active (running)' in result['output']
            
            # Get version
            version_result = self.execute_command('asterisk -V')
            version = version_result['output'].strip() if version_result['success'] else 'Unknown'
            
            # Get active channels
            channels_result = self.execute_command('asterisk -rx "core show channels"', sudo=True)
            active_channels = 0
            if channels_result['success']:
                for line in channels_result['output'].split('\n'):
                    if 'active channel' in line.lower():
                        parts = line.split()
                        if parts:
                            active_channels = int(parts[0])
                        break
            
            return {
                'running': is_running,
                'version': version,
                'active_channels': active_channels,
                'host': self.host
            }
        except Exception as e:
            logger.error(f"Failed to get Asterisk status: {e}")
            return {
                'running': False,
                'version': 'Unknown',
                'active_channels': 0,
                'host': self.host
            }
    
    def configure_sip_trunks(self, sip_accounts: list, progress_callback: Optional[Callable] = None) -> bool:
        """
        Configure SIP trunks (PJSIP)
        
        Args:
            sip_accounts: List of SIPAccount objects from database
            progress_callback: Optional progress callback
        
        Returns:
            Success status
        """
        try:
            if progress_callback:
                progress_callback(f"📞 Configuring {len(sip_accounts)} SIP trunk(s)...")
            
            # Generate PJSIP config
            pjsip_config = AsteriskConfig.generate_sip_config(sip_accounts)
            
            # Write to temp file
            temp_path = '/tmp/pjsip.conf'
            sftp = self.client.open_sftp()
            with sftp.file(temp_path, 'w') as f:
                f.write(pjsip_config)
            sftp.close()
            
            # Move to proper location with sudo
            result = self.execute_command(f'mv {temp_path} /etc/asterisk/pjsip.conf', sudo=True)
            if not result['success']:
                logger.error(f"Failed to write pjsip.conf: {result['error']}")
                return False
            
            # Set permissions
            self.execute_command('chown asterisk:asterisk /etc/asterisk/pjsip.conf', sudo=True)
            self.execute_command('chmod 640 /etc/asterisk/pjsip.conf', sudo=True)
            
            # Reload PJSIP
            if progress_callback:
                progress_callback("🔄 Reloading PJSIP...")
            
            reload_result = self.execute_command('asterisk -rx "pjsip reload"', sudo=True)
            
            # Check registration status
            time.sleep(2)
            reg_result = self.execute_command('asterisk -rx "pjsip show registrations"', sudo=True)
            
            if progress_callback:
                if 'Registered' in reg_result['output']:
                    progress_callback("✅ SIP trunk(s) registered successfully!")
                else:
                    progress_callback("⚠️ Check SIP registration status")
            
            return True
            
        except Exception as e:
            logger.error(f"SIP configuration failed: {e}")
            if progress_callback:
                progress_callback(f"❌ SIP config error: {str(e)}")
            return False
    
    def upload_audio_file(self, local_path: str, remote_filename: str, 
                         progress_callback: Optional[Callable] = None) -> bool:
        """
        Upload audio file to Asterisk sounds directory
        
        Args:
            local_path: Path to local audio file
            remote_filename: Filename on VPS (without extension)
            progress_callback: Optional progress callback
        
        Returns:
            Success status
        """
        try:
            if not os.path.exists(local_path):
                logger.error(f"Local file not found: {local_path}")
                return False
            
            if progress_callback:
                progress_callback(f"📤 Uploading {remote_filename}...")
            
            # Determine remote path
            remote_dir = '/var/lib/asterisk/sounds/campaigns'
            remote_path = f'{remote_dir}/{remote_filename}'
            
            # Ensure extension
            if not remote_filename.endswith(('.wav', '.gsm', '.ulaw')):
                remote_path += '.wav'
            
            # Create directory if needed
            self.execute_command(f'mkdir -p {remote_dir}', sudo=True)
            
            # Upload via SFTP to temp location
            temp_path = f'/tmp/{os.path.basename(remote_path)}'
            sftp = self.client.open_sftp()
            sftp.put(local_path, temp_path)
            sftp.close()
            
            # Move with sudo and set permissions
            self.execute_command(f'mv {temp_path} {remote_path}', sudo=True)
            self.execute_command(f'chown asterisk:asterisk {remote_path}', sudo=True)
            self.execute_command(f'chmod 644 {remote_path}', sudo=True)
            
            if progress_callback:
                progress_callback(f"✅ Uploaded {remote_filename}")
            
            return True
            
        except Exception as e:
            logger.error(f"Audio upload failed: {e}")
            if progress_callback:
                progress_callback(f"❌ Upload error: {str(e)}")
            return False
    
    def setup_campaign_context(self, campaign, progress_callback: Optional[Callable] = None) -> bool:
        """
        Setup Asterisk dialplan context for a campaign
        
        Args:
            campaign: Campaign object from database
            progress_callback: Optional progress callback
        
        Returns:
            Success status
        """
        try:
            if progress_callback:
                progress_callback(f"⚙️ Setting up campaign {campaign.id}...")
            
            # Read current dialplan
            result = self.execute_command('cat /etc/asterisk/extensions.conf', sudo=True)
            if not result['success']:
                logger.error("Failed to read extensions.conf")
                return False
            
            current_dialplan = result['output']
            
            # Generate campaign context
            campaign_context = AsteriskConfig.generate_campaign_context(campaign)
            
            # Check if context already exists
            context_marker = f"[campaign-{campaign.id}]"
            if context_marker in current_dialplan:
                # Remove old context
                lines = current_dialplan.split('\n')
                new_lines = []
                skip = False
                
                for line in lines:
                    if line.strip() == context_marker:
                        skip = True
                        continue
                    if skip and line.strip().startswith('[') and line.strip() != context_marker:
                        skip = False
                    if not skip:
                        new_lines.append(line)
                
                current_dialplan = '\n'.join(new_lines)
            
            # Append new context
            updated_dialplan = current_dialplan.rstrip() + '\n\n' + campaign_context
            
            # Write updated dialplan
            temp_path = '/tmp/extensions.conf'
            sftp = self.client.open_sftp()
            with sftp.file(temp_path, 'w') as f:
                f.write(updated_dialplan)
            sftp.close()
            
            # Move with sudo
            self.execute_command(f'mv {temp_path} /etc/asterisk/extensions.conf', sudo=True)
            self.execute_command('chown asterisk:asterisk /etc/asterisk/extensions.conf', sudo=True)
            
            # Reload dialplan
            if progress_callback:
                progress_callback("🔄 Reloading dialplan...")
            
            self.execute_command('asterisk -rx "dialplan reload"', sudo=True)
            time.sleep(1)
            
            if progress_callback:
                progress_callback(f"✅ Campaign {campaign.id} context ready!")
            
            return True
            
        except Exception as e:
            logger.error(f"Campaign setup failed: {e}")
            if progress_callback:
                progress_callback(f"❌ Setup error: {str(e)}")
            return False
    
    def remove_campaign_context(self, campaign_id: int) -> bool:
        """Remove campaign context from dialplan"""
        try:
            # Read current dialplan
            result = self.execute_command('cat /etc/asterisk/extensions.conf', sudo=True)
            if not result['success']:
                return False
            
            current_dialplan = result['output']
            context_marker = f"[campaign-{campaign_id}]"
            
            if context_marker not in current_dialplan:
                return True  # Already removed
            
            # Remove context
            lines = current_dialplan.split('\n')
            new_lines = []
            skip = False
            
            for line in lines:
                if line.strip() == context_marker:
                    skip = True
                    continue
                if skip and line.strip().startswith('[') and line.strip() != context_marker:
                    skip = False
                if not skip:
                    new_lines.append(line)
            
            updated_dialplan = '\n'.join(new_lines)
            
            # Write updated dialplan
            temp_path = '/tmp/extensions.conf'
            sftp = self.client.open_sftp()
            with sftp.file(temp_path, 'w') as f:
                f.write(updated_dialplan)
            sftp.close()
            
            self.execute_command(f'mv {temp_path} /etc/asterisk/extensions.conf', sudo=True)
            self.execute_command('asterisk -rx "dialplan reload"', sudo=True)
            
            logger.info(f"Removed campaign {campaign_id} context")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove campaign context: {e}")
            return False
    
    def originate_call(self, phone_number: str, campaign_id: int, 
                      sip_trunk: str, caller_id: str = None) -> Dict:
        """
        Originate an outbound call via AMI
        
        Args:
            phone_number: Destination phone number
            campaign_id: Campaign ID
            sip_trunk: SIP trunk name
            caller_id: Caller ID to present
        
        Returns:
            Dict with success status and call info
        """
        try:
            # Format phone number (remove non-digits)
            clean_number = ''.join(filter(str.isdigit, phone_number))
            
            # Build AMI originate command
            context = f"campaign-{campaign_id}"
            channel = f"PJSIP/{clean_number}@{sip_trunk}"
            
            if caller_id:
                callerid_param = f'CallerID="{caller_id}" <{caller_id}>'
            else:
                callerid_param = ""
            
            cmd = f'asterisk -rx "channel originate {channel} extension s@{context} {callerid_param}"'
            
            result = self.execute_command(cmd, sudo=True)
            
            if result['success'] or 'originated' in result['output'].lower():
                logger.info(f"Call originated to {phone_number}")
                return {
                    'success': True,
                    'phone_number': phone_number,
                    'channel': channel
                }
            else:
                logger.error(f"Call origination failed: {result['error']}")
                return {
                    'success': False,
                    'error': result['error']
                }
                
        except Exception as e:
            logger.error(f"Originate call failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_call_stats(self) -> Dict:
        """Get current call statistics"""
        try:
            # Active channels
            channels = self.execute_command('asterisk -rx "core show channels"', sudo=True)
            active_calls = 0
            
            if channels['success']:
                for line in channels['output'].split('\n'):
                    if 'active channel' in line.lower():
                        parts = line.split()
                        if parts:
                            active_calls = int(parts[0])
                        break
            
            # SIP peers status
            peers = self.execute_command('asterisk -rx "pjsip show endpoints"', sudo=True)
            registered_trunks = 0
            
            if peers['success']:
                for line in peers['output'].split('\n'):
                    if 'Avail' in line or 'Online' in line:
                        registered_trunks += 1
            
            return {
                'active_calls': active_calls,
                'registered_trunks': registered_trunks,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to get call stats: {e}")
            return {
                'active_calls': 0,
                'registered_trunks': 0,
                'error': str(e)
            }
