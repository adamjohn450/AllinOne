#!/usr/bin/env python3
"""
Test script to make a test call once SIP is working
Run this after SIP trunk registration is successful
"""
import sys
sys.path.insert(0, '/root/autodialer_bot')

from database import SessionLocal, Campaign, PhoneNumber, VPSServer, User
from datetime import datetime

def create_test_campaign():
    """Create a test campaign with one phone number"""
    db = SessionLocal()
    
    try:
        # Get the first user
        user = db.query(User).first()
        if not user:
            print("❌ No users found. Run /start in Telegram first.")
            return False
        
        print(f"✅ Found user: {user.telegram_id}")
        
        # Get the VPS server
        vps = db.query(VPSServer).first()
        if not vps:
            print("❌ No VPS servers found. Add a VPS first.")
            return False
        
        print(f"✅ Found VPS: {vps.host}")
        
        # Check if test campaign already exists
        existing = db.query(Campaign).filter_by(name="SIP Test Campaign").first()
        if existing:
            print(f"⚠️ Test campaign already exists (ID: {existing.id})")
            campaign = existing
        else:
            # Create test campaign
            campaign = Campaign(
                user_id=user.id,
                server_id=vps.id,
                name="SIP Test Campaign",
                tts_transfer="Press 1 to be transferred, or press 2 for a callback.",
                tts_callback="Thank you. We will call you back soon. Goodbye.",
                transfer_number="12633783363",  # Test number provided
                max_concurrent=1,
                status='pending',
                created_at=datetime.utcnow()
            )
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            print(f"✅ Created test campaign (ID: {campaign.id})")
        
        # Check if test phone number exists
        test_phone = "12633783363"
        existing_phone = db.query(PhoneNumber).filter_by(
            campaign_id=campaign.id,
            phone_number=test_phone
        ).first()
        
        if existing_phone:
            print(f"⚠️ Test phone number already exists")
            existing_phone.status = 'pending'
            existing_phone.attempts = 0
            db.commit()
        else:
            # Add test phone number
            phone = PhoneNumber(
                campaign_id=campaign.id,
                phone_number=test_phone,
                status='pending',
                attempts=0,
                added_at=datetime.utcnow()
            )
            db.add(phone)
            db.commit()
            print(f"✅ Added test phone number: {test_phone}")
        
        print(f"\n" + "=" * 60)
        print(f"✅ TEST CAMPAIGN READY!")
        print(f"=" * 60)
        print(f"Campaign ID: {campaign.id}")
        print(f"Campaign Name: {campaign.name}")
        print(f"Transfer Number: {campaign.transfer_number}")
        print(f"=" * 60)
        print(f"\n📱 To start the campaign:")
        print(f"1. Open Telegram bot")
        print(f"2. Go to 'My Campaigns'")
        print(f"3. Select 'SIP Test Campaign'")
        print(f"4. Click 'Start Campaign'")
        print(f"\nThe bot will call {test_phone} and play the TTS message.")
        print(f"When the call is answered, it will wait for:")
        print(f"  • Press 1 → Transfer to {campaign.transfer_number}")
        print(f"  • Press 2 → Request callback")
        print(f"\n" + "=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("  Creating Test Campaign")
    print("=" * 60)
    
    success = create_test_campaign()
    
    sys.exit(0 if success else 1)
