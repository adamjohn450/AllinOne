#!/usr/bin/env python3
"""
Deploy pre-recorded audio files for campaigns
Converts MP3 to Asterisk-compatible format
"""
import sys
sys.path.insert(0, '/root/autodialer_bot')

from database import SessionLocal, Campaign
import os
import shutil

def deploy_audio_files(campaign_id):
    """Deploy pre-recorded audio files for a campaign"""
    db = SessionLocal()
    
    try:
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            print(f"❌ Campaign {campaign_id} not found")
            return False
        
        print(f"✅ Found campaign: {campaign.name}")
        print(f"📂 Deploying pre-recorded audio files...")
        
        # Directory for audio files - MUST be /usr/share/asterisk/sounds/
        sounds_dir = "/usr/share/asterisk/sounds"
        source_dir = "/root/autodialer_bot/audio"
        
        # Deploy cracrypto.mp3 (main message)
        cracrypto_source = f"{source_dir}/cracrypto.mp3"
        if os.path.exists(cracrypto_source):
            print(f"🎤 Converting cracrypto.mp3...")
            
            # Convert to Asterisk format (8kHz mono ulaw)
            os.system(f"ffmpeg -i {cracrypto_source} -ar 8000 -ac 1 -f mulaw {sounds_dir}/cracrypto.ulaw -y 2>/dev/null")
            os.system(f"cp {sounds_dir}/cracrypto.ulaw {sounds_dir}/cracrypto.pcm")
            
            print(f"   ✅ Deployed: cracrypto")
        else:
            print(f"   ⚠️  Warning: cracrypto.mp3 not found in {source_dir}")
        
        # Deploy thankyou.mp3 (after pressing 1)
        thankyou_source = f"{source_dir}/thankyou.mp3"
        if os.path.exists(thankyou_source):
            print(f"🎤 Converting thankyou.mp3...")
            
            # Convert to Asterisk format
            os.system(f"ffmpeg -i {thankyou_source} -ar 8000 -ac 1 -f mulaw {sounds_dir}/thankyou.ulaw -y 2>/dev/null")
            os.system(f"cp {sounds_dir}/thankyou.ulaw {sounds_dir}/thankyou.pcm")
            
            print(f"   ✅ Deployed: thankyou")
        else:
            print(f"   ⚠️  Warning: thankyou.mp3 not found in {source_dir}")
        
        # Set permissions
        os.system(f"chown asterisk:asterisk {sounds_dir}/cracrypto* {sounds_dir}/thankyou* 2>/dev/null")
        os.system(f"chmod 644 {sounds_dir}/cracrypto* {sounds_dir}/thankyou* 2>/dev/null")
        
        print("✅ Audio deployment complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def generate_campaign_tts(campaign_id, host, username, password, port=22):
    """Generate Asterisk dialplan and deploy audio files for campaign"""
    import paramiko
    from asterisk_config import AsteriskConfig
    from database import Campaign, VPSServer
    
    db = SessionLocal()
    
    try:
        # Get campaign and VPS info
        campaign = db.query(Campaign).filter_by(id=campaign_id).first()
        if not campaign:
            print(f"❌ Campaign {campaign_id} not found")
            return False
        
        vps = db.query(VPSServer).filter_by(id=campaign.server_id).first()
        if not vps:
            print(f"❌ VPS for campaign {campaign_id} not found")
            return False
        
        print(f"✅ Regenerating Asterisk dialplan for campaign {campaign_id}")
        
        # Connect to VPS via SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(
                hostname=vps.host,
                port=vps.ssh_port or 22,
                username=vps.ssh_username or 'root',
                password=vps.ssh_password,
                timeout=10
            )
            
            # Get all campaigns for this VPS
            campaigns = db.query(Campaign).filter_by(server_id=vps.id).all()
            print(f"📋 Found {len(campaigns)} campaigns for this VPS")
            
            # Generate dialplan with all campaigns
            dialplan = AsteriskConfig.generate_dialplan(campaigns)
            
            # Write to /etc/asterisk/extensions.conf
            sftp = ssh.open_sftp()
            with sftp.file('/etc/asterisk/extensions.conf', 'w') as f:
                f.write(dialplan)
            sftp.close()
            
            print(f"✅ Dialplan written to /etc/asterisk/extensions.conf")
            
            # Reload Asterisk dialplan
            stdin, stdout, stderr = ssh.exec_command('asterisk -rx "dialplan reload"')
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if output:
                print(f"✅ Asterisk response: {output}")
            if error:
                print(f"⚠️ Stderr: {error}")
            
            # Deploy audio files (already in /usr/share/asterisk/sounds/)
            deploy_audio_files(campaign_id)
            
            ssh.close()
            return True
            
        except Exception as e:
            print(f"❌ SSH Error: {e}")
            if ssh:
                ssh.close()
            return False
        
    except Exception as e:
        print(f"❌ Error generating dialplan: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    CAMPAIGN_ID = 1  # Default campaign ID
    
    print("=" * 60)
    print("  Deploy Audio Files for Campaign")
    print("=" * 60)
    
    success = deploy_audio_files(CAMPAIGN_ID)
    
    if success:
        print("\n✅ SUCCESS! Audio files deployed.")
    else:
        print("\n❌ FAILED! Check errors above.")
    
    sys.exit(0 if success else 1)
