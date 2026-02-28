#!/usr/bin/env python3
"""
Script to regenerate Asterisk configuration with all campaigns
"""
import sys
sys.path.insert(0, '/root/autodialer_bot')

from database import SessionLocal, Campaign, VPSServer
from vps_manager import VPSManager

def regenerate_config(vps_id):
    """Regenerate Asterisk configuration"""
    db = SessionLocal()
    
    try:
        # Get VPS
        vps = db.query(VPSServer).filter_by(id=vps_id).first()
        if not vps:
            print(f"❌ VPS with ID {vps_id} not found")
            return False
        
        print(f"✅ Found VPS: {vps.name or vps.host}")
        
        # Connect to VPS
        print(f"📡 Connecting to VPS {vps.host}...")
        vps_mgr = VPSManager(
            host=vps.host,
            username=vps.ssh_username or 'root',
            password=vps.ssh_password
        )
        
        if not vps_mgr.connect():
            print("❌ Failed to connect to VPS")
            return False
        
        print("✅ Connected to VPS")
        
        # Get all campaigns for this VPS
        campaigns = db.query(Campaign).filter_by(server_id=vps_id).all()
        print(f"📋 Found {len(campaigns)} campaigns")
        
        # Regenerate Asterisk configuration
        print("🔧 Regenerating Asterisk configuration...")
        if vps_mgr.configure_asterisk(campaigns):
            print("✅ Asterisk configuration updated successfully!")
            
            # Reload dialplan
            print("🔄 Reloading Asterisk dialplan...")
            stdin, stdout, stderr = vps_mgr.ssh.exec_command('asterisk -rx "dialplan reload"')
            output = stdout.read().decode()
            print(f"   {output.strip()}")
            
            print("✅ Configuration complete!")
            return True
        else:
            print("❌ Failed to configure Asterisk")
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    VPS_ID = 2
    
    print("=" * 60)
    print("  Regenerate Asterisk Configuration")
    print("=" * 60)
    
    success = regenerate_config(VPS_ID)
    
    if success:
        print("\n✅ SUCCESS! Asterisk configuration updated.")
    else:
        print("\n❌ FAILED! Check errors above.")
    
    sys.exit(0 if success else 1)
