"""
Asterisk Configuration Generator
Handles all Asterisk configuration file generation and management
"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AsteriskConfig:
    """Generate Asterisk configuration files"""
    
    @staticmethod
    def generate_ami_config(username: str = 'autodialer', password: str = None) -> str:
        """
        Generate AMI (Asterisk Manager Interface) configuration
        
        Args:
            username: AMI username
            password: AMI password (generated if not provided)
        
        Returns:
            manager.conf content
        """
        if not password:
            import secrets
            password = secrets.token_urlsafe(16)
        
        return f"""[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[{username}]
secret = {password}
deny = 0.0.0.0/0.0.0.0
permit = 0.0.0.0/0.0.0.0
read = all
write = all
writetimeout = 5000
"""
    
    @staticmethod
    def generate_sip_config(sip_accounts: list) -> str:
        """
        Generate PJSIP configuration for SIP trunks
        
        Args:
            sip_accounts: List of SIPAccount objects
        
        Returns:
            pjsip.conf content
        """
        config = """[global]
type=global
debug=no

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0

[transport-tcp]
type=transport
protocol=tcp
bind=0.0.0.0

"""
        
        for account in sip_accounts:
            if account.provider_type == 'google_voice':
                # Google Voice via Obihai gateway
                config += f"""
; Google Voice: {account.name}
[{account.name}]
type=endpoint
context=from-trunk
disallow=all
allow=ulaw
allow=alaw
from_user={account.google_phone}
outbound_auth={account.name}-auth
aors={account.name}

[{account.name}-auth]
type=auth
auth_type=userpass
username={account.google_email}
password={account.google_password}

[{account.name}]
type=aor
contact=sip:{account.google_phone}@gvgw.obihai.com

[{account.name}-reg]
type=registration
transport=transport-udp
outbound_auth={account.name}-auth
server_uri=sip:gvgw.obihai.com
client_uri=sip:{account.google_phone}@gvgw.obihai.com
retry_interval=60

"""
            else:
                # Standard SIP trunk
                config += f"""
; SIP Trunk: {account.name}
[{account.name}]
type=endpoint
context=from-trunk
disallow=all
allow=ulaw
allow=alaw
allow=g722
outbound_auth={account.name}-auth
aors={account.name}
direct_media=no
from_user={account.sip_username}

[{account.name}-auth]
type=auth
auth_type=userpass
username={account.sip_username}
password={account.sip_password}

[{account.name}]
type=aor
contact=sip:{account.sip_username}@{account.sip_server}:{account.sip_port}

[{account.name}-reg]
type=registration
transport=transport-udp
outbound_auth={account.name}-auth
server_uri=sip:{account.sip_server}:{account.sip_port}
client_uri=sip:{account.sip_username}@{account.sip_server}
retry_interval=60

"""
        
        return config
    
    @staticmethod
    def generate_dialplan(campaigns: list = None) -> str:
        """
        Generate dialplan (extensions.conf) for campaigns
        
        Args:
            campaigns: List of Campaign objects
        
        Returns:
            extensions.conf content
        """
        config = """[general]
static=yes
writeprotect=no
autofallthrough=yes

[globals]

"""
        
        # Base context for incoming calls from trunk
        config += """
[from-trunk]
exten => _X.,1,NoOp(Incoming call from trunk)
    same => n,Answer()
    same => n,Playback(tt-monkeys)
    same => n,Hangup()

"""
        
        # Campaign contexts
        if campaigns:
            for campaign in campaigns:
                config += AsteriskConfig.generate_campaign_context(campaign)
        else:
            # Default template campaign
            config += """
[campaign-template]
; Template for campaign dialplan
exten => s,1,Answer()
    same => n,Wait(1)
    same => n,Set(CAMPAIGN_ID=${ARG1})
    same => n,Set(PHONE_NUMBER=${CALLERID(num)})
    same => n,Playback(${TTS_TRANSFER})
    same => n,WaitExten(30)
    same => n,Goto(timeout,1)

; Option 1 - Transfer
exten => 1,1,NoOp(Transfer requested)
    same => n,Set(ACTION=pressed_1)
    same => n,UserEvent(CampaignAction,Campaign:${CAMPAIGN_ID},Phone:${PHONE_NUMBER},Action:pressed_1)
    same => n,Playback(please-wait)
    same => n,Dial(PJSIP/${TRANSFER_NUMBER}@${SIP_TRUNK},60,rtT)
    same => n,Hangup()

; Option 2 - Callback
exten => 2,1,NoOp(Callback requested)
    same => n,Set(ACTION=pressed_2)
    same => n,UserEvent(CampaignAction,Campaign:${CAMPAIGN_ID},Phone:${PHONE_NUMBER},Action:pressed_2)
    same => n,Playback(${TTS_CALLBACK})
    same => n,Wait(2)
    same => n,Hangup()

; Timeout - no response
exten => timeout,1,NoOp(No response)
    same => n,UserEvent(CampaignAction,Campaign:${CAMPAIGN_ID},Phone:${PHONE_NUMBER},Action:no_response)
    same => n,Playback(goodbye)
    same => n,Hangup()

; Invalid input
exten => i,1,Playback(invalid)
    same => n,Goto(s,3)

; Hangup handler
exten => h,1,NoOp(Call ended)
    same => n,UserEvent(CampaignEnd,Campaign:${CAMPAIGN_ID},Phone:${PHONE_NUMBER},Duration:${CDR(duration)})
    same => n,Hangup()

"""
        
        return config
    
    @staticmethod
    @staticmethod
    def generate_campaign_context(campaign) -> str:
        """
        Generate dialplan context for specific campaign with missed transfer handling
        
        Args:
            campaign: Campaign object
        
        Returns:
            Dialplan context string
        """
        context_name = f"campaign-{campaign.id}"
        
        # Get trunk name from SIP account
        if hasattr(campaign, 'sip_account') and campaign.sip_account:
            trunk_name = campaign.sip_account.name
        else:
            trunk_name = "trunk_2"  # Default to trunk_2
        
        # Get audio template from campaign (stored in tts_transfer field)
        audio_template = campaign.tts_transfer if campaign.tts_transfer else 'cracrypto'
        
        config = f"""
; Campaign: {campaign.name} (ID: {campaign.id})
[{context_name}]
exten => s,1,Answer()
    same => n,Wait(1)
    same => n,Set(CAMPAIGN_ID={campaign.id})
    same => n,Set(SIP_TRUNK={trunk_name})
    same => n,UserEvent(CampaignCall,CampaignID: ${{CAMPAIGN_ID}},PhoneNumber: ${{PHONE_NUMBER}},Status: answered)
    same => n,Playback({audio_template})
    same => n,WaitExten(30)
    same => n,Goto(timeout,1)

; Option 1 - Pressed 1 (Notification Only - No Transfer)
exten => 1,1,NoOp(Pressed 1 by ${{PHONE_NUMBER}})
    same => n,UserEvent(CampaignCall,CampaignID: ${{CAMPAIGN_ID}},PhoneNumber: ${{PHONE_NUMBER}},Status: pressed_1)
    same => n,Playback(thankyou)
    same => n,Wait(1)
    same => n,Hangup()

; Option 2 - Pressed 2 (Ignored)
exten => 2,1,NoOp(Pressed 2 by ${{PHONE_NUMBER}})
    same => n,Playback(thankyou)
    same => n,Hangup()

; Timeout - no response
exten => timeout,1,NoOp(Call timeout - no input from ${{PHONE_NUMBER}})
    same => n,UserEvent(CampaignCall,CampaignID: ${{CAMPAIGN_ID}},PhoneNumber: ${{PHONE_NUMBER}},Status: no_response)
    same => n,Playback(goodbye)
    same => n,Hangup()

; Invalid input
exten => i,1,NoOp(Invalid input)
    same => n,Playback(invalid)
    same => n,Goto(s,7)

; Hangup handler - captures SIP/cause code for every call outcome
exten => h,1,NoOp(Call ended for campaign {campaign.id} cause=${{HANGUPCAUSE}})
    same => n,UserEvent(CampaignCall,CampaignID: ${{CAMPAIGN_ID}},PhoneNumber: ${{PHONE_NUMBER}},Status: hangup,Duration: ${{CDR(duration)}},Cause: ${{HANGUPCAUSE}},CauseTxt: ${{HANGUPCAUSE_TXT}})
    same => n,Hangup()

"""
        return config
    

    @staticmethod
    def generate_modules_config() -> str:
        """Generate modules.conf for required modules"""
        return """[modules]
autoload=yes

; Core modules
load => res_musiconhold.so
load => app_dial.so
load => app_playback.so
load => app_voicemail.so
load => chan_pjsip.so
load => res_pjsip.so
load => res_pjsip_session.so
load => res_pjsip_outbound_registration.so
load => res_pjsip_authenticator_digest.so
load => app_mixmonitor.so
load => app_queue.so

; Manager interface
load => manager.so

; CDR
load => cdr_csv.so
load => cdr_custom.so

noload => chan_sip.so
"""
    
    @staticmethod
    def generate_rtp_config() -> str:
        """Generate RTP configuration"""
        return """[general]
rtpstart=10000
rtpend=20000
strictrtp=yes
icesupport=yes
stunaddr=stun.l.google.com:19302
"""
    
    @staticmethod
    def generate_logger_config() -> str:
        """Generate logger configuration"""
        return """[general]
dateformat=%F %T

[logfiles]
console => notice,warning,error
messages => notice,warning,error
full => notice,warning,error,debug,verbose
"""
    
    @staticmethod
    def generate_cdr_config() -> str:
        """Generate CDR (Call Detail Records) configuration"""
        return """[general]
enable=yes
unanswered = yes
congestion = yes
batch=no
size=100
time=300
scheduleronly=no
safeshutdown=yes
"""
    
    @staticmethod
    def generate_musiconhold_config() -> str:
        """Generate Music on Hold configuration"""
        return """[default]
mode=files
directory=/var/lib/asterisk/moh
random=yes
sort=alpha

[autodialer]
mode=files
directory=/var/lib/asterisk/moh
random=yes
sort=alpha
"""
    
    @staticmethod
    def generate_install_script(os_type: str) -> str:
        """
        Generate comprehensive Asterisk installation script
        
        Args:
            os_type: OS type (ubuntu, debian, centos, rhel)
        
        Returns:
            Bash script content
        """
        if os_type in ['ubuntu', 'debian']:
            return """#!/bin/bash
# Asterisk Auto-Installation Script for Ubuntu/Debian
set -e

echo "========================================="
echo "  Asterisk Auto-Dialer Installation"
echo "========================================="

# Update system
echo "📦 Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

# Install dependencies
echo "📦 Installing dependencies..."
apt-get install -y -qq \\
    build-essential \\
    wget \\
    subversion \\
    libssl-dev \\
    libncurses5-dev \\
    libnewt-dev \\
    libxml2-dev \\
    linux-headers-$(uname -r) \\
    libsqlite3-dev \\
    uuid-dev \\
    libjansson-dev \\
    libedit-dev

# Install Asterisk from repo (faster than compiling)
echo "📦 Installing Asterisk..."
apt-get install -y -qq asterisk

# Install additional packages
apt-get install -y -qq \\
    asterisk-config \\
    asterisk-core-sounds-en \\
    asterisk-core-sounds-en-gsm \\
    asterisk-modules \\
    asterisk-voicemail

# Create directories
echo "📁 Creating directories..."
mkdir -p /var/lib/asterisk/sounds/custom
mkdir -p /var/lib/asterisk/sounds/campaigns
mkdir -p /var/log/asterisk
mkdir -p /var/spool/asterisk

# Set permissions
chown -R asterisk:asterisk /var/lib/asterisk
chown -R asterisk:asterisk /var/log/asterisk
chown -R asterisk:asterisk /var/spool/asterisk
chown -R asterisk:asterisk /etc/asterisk

# Enable and start Asterisk
echo "🚀 Starting Asterisk..."
systemctl enable asterisk
systemctl start asterisk

# Wait for Asterisk to start
sleep 5

# Check status
if systemctl is-active --quiet asterisk; then
    echo "✅ Asterisk installed and running!"
    asterisk -V
else
    echo "❌ Asterisk installation may have failed"
    exit 1
fi

echo "========================================="
echo "  Installation Complete!"
echo "========================================="
"""
        
        elif os_type in ['centos', 'rhel']:
            return """#!/bin/bash
# Asterisk Auto-Installation Script for CentOS/RHEL
set -e

echo "========================================="
echo "  Asterisk Auto-Dialer Installation"
echo "========================================="

# Enable EPEL
echo "📦 Enabling EPEL repository..."
yum install -y epel-release

# Update system
echo "📦 Updating system packages..."
yum update -y -q

# Install dependencies
echo "📦 Installing dependencies..."
yum install -y -q \\
    wget \\
    gcc \\
    gcc-c++ \\
    make \\
    openssl-devel \\
    ncurses-devel \\
    newt-devel \\
    libxml2-devel \\
    kernel-devel \\
    sqlite-devel \\
    libuuid-devel \\
    jansson-devel

# Install Asterisk
echo "📦 Installing Asterisk..."
yum install -y -q asterisk asterisk-configs

# Create directories
echo "📁 Creating directories..."
mkdir -p /var/lib/asterisk/sounds/custom
mkdir -p /var/lib/asterisk/sounds/campaigns
mkdir -p /var/log/asterisk
mkdir -p /var/spool/asterisk

# Set permissions
chown -R asterisk:asterisk /var/lib/asterisk
chown -R asterisk:asterisk /var/log/asterisk
chown -R asterisk:asterisk /var/spool/asterisk

# Enable and start
echo "🚀 Starting Asterisk..."
systemctl enable asterisk
systemctl start asterisk

# Wait for start
sleep 5

# Check status
if systemctl is-active --quiet asterisk; then
    echo "✅ Asterisk installed and running!"
    asterisk -V
else
    echo "❌ Asterisk installation may have failed"
    exit 1
fi

echo "========================================="
echo "  Installation Complete!"
echo "========================================="
"""
        
        return ""
    
    @staticmethod
    def validate_config(config_type: str, content: str) -> Dict:
        """
        Validate configuration syntax
        
        Args:
            config_type: Type of config (ami, sip, dialplan)
            content: Configuration content
        
        Returns:
            Dict with validation result
        """
        # Basic validation
        errors = []
        warnings = []
        
        if config_type == 'dialplan':
            # Check for basic dialplan syntax
            if '[' not in content:
                errors.append("No contexts defined")
            if 'exten =>' not in content and 'same =>' not in content:
                errors.append("No extensions defined")
        
        elif config_type == 'sip':
            # Check for basic SIP config
            if 'type=endpoint' not in content:
                warnings.append("No endpoints defined")
        
        elif config_type == 'ami':
            # Check AMI config
            if '[general]' not in content:
                errors.append("Missing [general] section")
            if 'enabled = yes' not in content:
                warnings.append("AMI may not be enabled")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
