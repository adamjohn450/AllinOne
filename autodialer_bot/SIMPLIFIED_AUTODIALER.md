# Autodialer Bot - Simplified Version

## Changes Made

### 1. **Simplified Campaign Creation Flow**
   - **Step 1:** Campaign Name
   - **Step 2:** Select TTS Template (Pre-made messages)
   - **Step 3:** Upload Phone List
   - **Campaign Created!**

### 2. **Pre-made TTS Templates**
   Located in `tts_templates.py`:
   - 🇨🇦 CRA - Tax Verification
   - 💰 NDAX - Account Verification  
   - 🏦 Bank - Security Alert
   - 🎁 Prize Winner Notification
   - 🛠️ Technical Support
   - ✏️ Custom Message (user can write their own)

### 3. **Notification-Only System**
   - **NO CALL TRANSFERS** - Bot does NOT connect calls
   - When someone presses 1, you receive a Telegram notification:
     ```
     📞 Phone number 2712482148 pressed 1
     
     Campaign: Tax Season 2026
     Timestamp: 2026-02-27 12:34:56
     ```

### 4. **Removed Features**
   - ❌ Transfer number input
   - ❌ Concurrent calls selection (default: 5)
   - ❌ Callback option (option 2)
   - ❌ Call transfer functionality

### 5. **How It Works Now**
   1. Bot calls phone numbers from your list
   2. Plays the TTS message (e.g., "Press 1 to speak with an agent...")
   3. If they press 1 → You get instant Telegram notification
   4. If they press 2 or no response → Call ends, no notification
   5. That's it!

## Usage

### Create a Campaign
```
/newcampaign
→ Enter campaign name
→ Select TTS template
→ Upload phone list
→ Done!
```

### Start Campaign
```
/campaigns
→ Select your campaign
→ Click "Start"
```

### Monitor Results
- You'll receive Telegram messages when someone presses 1
- View stats with `/campaigns`

## File Changes

1. **bot.py** - Simplified conversation flow
2. **ami_listener.py** - Added simple press-1 notifications
3. **tts_templates.py** - NEW: Pre-made TTS messages
4. **SIMPLIFIED_AUTODIALER.md** - This file

## Next Steps

The bot is now simplified to work as a notification system only. No transfers, no callbacks, just simple notifications when leads press 1.
