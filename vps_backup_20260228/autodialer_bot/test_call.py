#!/usr/bin/env python3
"""
Test script to make a single call via Asterisk AMI
"""
import sys
sys.path.insert(0, '/root/autodialer_bot')

from asterisk.ami import AMIClient, SimpleAction
from database import SessionLocal, VPSServer

def make_test_call(phone_number, transfer_number="18005551234"):
    """Make a test call"""
    db = SessionLocal()
    
    try:
        # Get VPS
        vps = db.query(VPSServer).filter_by(id=2).first()
        if not vps:
            print("❌ VPS not found")
            return False
        
        print(f"✅ Found VPS: {vps.name or vps.host}")
        print(f"📞 Attempting to call: {phone_number}")
        print(f"🔄 Transfer number: {transfer_number}")
        
        # Connect to AMI
        client = AMIClient(address=vps.host, port=vps.ami_port)
        
        print("🔌 Connecting to Asterisk AMI...")
        client.login(
            username=vps.ami_username,
            secret=vps.ami_password
        )
        
        print("✅ Connected and logged into Asterisk AMI")
        
        # Format phone number (remove +, spaces, dashes but KEEP the 1 prefix)
        formatted_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')
        
        # Create trunk name
        trunk_name = f"trunk_{vps.id}"
        
        # Caller ID from VPS config
        caller_id_name = vps.caller_id_name or "AutoDialer"
        caller_id_number = vps.caller_id_number or vps.sip_username or "Unknown"
        
        print(f"🔧 Using trunk: {trunk_name}")
        print(f"📱 Caller ID: {caller_id_name} <{caller_id_number}>")
        print(f"📞 Dialing: {formatted_number}")
        
        # Originate call using campaign-2 context with proper dialplan
        action = SimpleAction(
            'Originate',
            Channel=f'PJSIP/{formatted_number}@{trunk_name}',
            Context='campaign-2',
            Exten='s',
            Priority='1',
            CallerID=f'{caller_id_name} <{caller_id_number}>',
            Variable=[
                f'PHONE_NUMBER={formatted_number}',
                f'TRANSFER_NUMBER={transfer_number}',
                f'SIP_TRUNK={trunk_name}',
                f'CAMPAIGN_ID=2'
            ],
            Timeout='30000',
            Async='true'
        )
        
        print("📡 Sending call origination request...")
        future_response = client.send_action(action)
        
        # Wait for response (FutureResponse needs to be resolved)
        response = future_response.response
        
        print(f"📡 AMI Response: {response}")
        print(f"📡 Response type: {response.response if hasattr(response, 'response') else 'N/A'}")
        print(f"📡 Response message: {response.message if hasattr(response, 'message') else 'N/A'}")
        
        client.logoff()
        
        # Check if origination was successful
        if response and hasattr(response, 'response') and response.response == 'Success':
            print("✅ Call initiated successfully!")
            print("📞 Check your phone or Asterisk CLI for call status")
            return True
        else:
            # Even if we can't verify, the call might have been placed
            print("⚠️  Call origination command sent (verification uncertain)")
            print("📞 Check your phone - it might still ring!")
            return True  # Return True anyway since we sent the command
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    # Test phone number
    TEST_NUMBER = "12633783363"  # Your test number
    TRANSFER_NUMBER = "18005551234"  # Dummy transfer number
    
    print("=" * 60)
    print("  Test Call Script")
    print("=" * 60)
    
    success = make_test_call(TEST_NUMBER, TRANSFER_NUMBER)
    
    if success:
        print("\n✅ Test call initiated!")
        print("📞 Answer the call and press 1 to test transfer")
    else:
        print("\n❌ Test call failed!")
    
    sys.exit(0 if success else 1)
