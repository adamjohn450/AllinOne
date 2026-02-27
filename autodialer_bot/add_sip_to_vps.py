#!/usr/bin/env python3
"""
Script to add SIP credentials to existing VPS and configure Asterisk
"""
import sys
sys.path.insert(0, '/root/autodialer_bot')

from database import SessionLocal, VPSServer
from vps_manager import VPSManager
from asterisk_config import AsteriskConfig

def add_sip_to_vps(vps_id, sip_server, sip_username, sip_password, sip_port=5060):
    """Add SIP configuration to a VPS"""
    db = SessionLocal()
    
    try:
        # Get VPS
        vps = db.query(VPSServer).filter_by(id=vps_id).first()
        if not vps:
            print(f"❌ VPS with ID {vps_id} not found")
            return False
        
        print(f"✅ Found VPS: {vps.name or vps.host}")
        
        # Update VPS with SIP info
        vps.sip_type = 'sip'
        vps.sip_server = sip_server
        vps.sip_username = sip_username
        vps.sip_password = sip_password
        vps.sip_port = sip_port
        vps.caller_id_name = 'AutoDialer'
        vps.caller_id_number = sip_username
        
        db.commit()
        print(f"✅ Updated database with SIP credentials")
        
        # Create SIP account object for configuration
        class SIPAccountTemp:
            def __init__(self, vps):
                self.name = f"trunk_{vps.id}"
                self.provider_type = 'sip'
                self.sip_server = vps.sip_server
                self.sip_username = vps.sip_username
                self.sip_password = vps.sip_password
                self.sip_port = vps.sip_port
        
        sip_account = SIPAccountTemp(vps)
        
        # Connect to VPS
        print(f"📡 Connecting to VPS {vps.host}...")
        vps_mgr = VPSManager(
            host=vps.host,
            username=vps.ssh_username,
            password=vps.ssh_password,
            port=vps.ssh_port
        )
        
        if not vps_mgr.connect():
            print(f"❌ Failed to connect to VPS")
            return False
        
        print(f"✅ Connected to VPS")
        
        # Configure SIP on Asterisk
        print(f"📞 Configuring SIP trunk on Asterisk...")
        success = vps_mgr.configure_sip_trunks([sip_account])
        
        if success:
            print(f"✅ SIP trunk configured successfully!")
            
            # Test registration
            print(f"🔍 Checking SIP registration...")
            result = vps_mgr.execute_command('asterisk -rx "pjsip show registrations"', sudo=True)
            print(f"\n{result['output']}")
            
            if 'Registered' in result['output']:
                print(f"✅ SIP trunk registered!")
            else:
                print(f"⚠️ SIP trunk may not be registered. Check configuration.")
        else:
            print(f"❌ SIP configuration failed")
            return False
        
        vps_mgr.disconnect()
        print(f"✅ Done!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    # Test SIP credentials provided by user
    SIP_SERVER = "185.235.143.10"
    SIP_USERNAME = "48337"
    SIP_PASSWORD = "71d12f3b01559"
    SIP_PORT = 5060
    
    print("=" * 60)
    print("  Adding SIP Credentials to VPS")
    print("=" * 60)
    print(f"SIP Server: {SIP_SERVER}")
    print(f"SIP Username: {SIP_USERNAME}")
    print(f"SIP Port: {SIP_PORT}")
    print("=" * 60)
    
    # Assuming VPS ID is 2 (check your database)
    VPS_ID = 2
    
    success = add_sip_to_vps(VPS_ID, SIP_SERVER, SIP_USERNAME, SIP_PASSWORD, SIP_PORT)
    
    if success:
        print("\n✅ SUCCESS! You can now create campaigns and make calls.")
    else:
        print("\n❌ FAILED! Check the errors above.")
    
    sys.exit(0 if success else 1)
