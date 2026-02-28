# Autodialer - Final Simplified Version

## Overview
The autodialer now uses pre-recorded audio files instead of TTS generation. It only sends notifications when someone presses 1 - no actual call transfers.

## Audio Files

### 1. cracrypto.mp3 (Main Message)
- **Location:** `/root/autodialer_bot/audio/cracrypto.mp3`
- **Deployed to:** `/usr/share/asterisk/sounds/cracrypto.{ulaw,pcm}`
- **Purpose:** First message played to the recipient
- **Should contain:** Instructions to press 1

### 2. thankyou.mp3 (Thank You Message)
- **Location:** `/root/autodialer_bot/audio/thankyou.mp3`
- **Deployed to:** `/usr/share/asterisk/sounds/thankyou.{ulaw,pcm}`
- **Purpose:** Played after someone presses 1
- **Should contain:** Thank you message

## Campaign Flow

```
1. Bot calls phone number
          ↓
2. Plays "cracrypto.mp3"
   (CRA crypto verification message with "Press 1" instruction)
          ↓
3. Waits for DTMF input (30 seconds)
          ↓
4a. If press 1:                    4b. If no response:
    → Play "thankyou.mp3"              → Hang up
    → Send Telegram notification       → No notification
    → Hang up
```

## Telegram Notification

When someone presses 1, you receive:
```
📞 Phone number 2712482148 pressed 1

Campaign: Tax Season 2026
Timestamp: 2026-02-27 12:34:56
```

## Campaign Creation (Simplified)

```
/newcampaign

Step 1: Enter campaign name
        ↓
Step 2: Upload phone list (.txt file or comma-separated)
        ↓
Campaign Created!
```

**No TTS selection needed** - all campaigns use the same pre-recorded audio files.

## How to Update Audio Files

If you want to change the audio messages:

1. Upload new MP3 files to `/root/autodialer_bot/audio/`
   - `cracrypto.mp3` (main message)
   - `thankyou.mp3` (thank you message)

2. Convert to Asterisk format:
   ```bash
   cd /root/autodialer_bot/audio
   
   # Convert cracrypto
   ffmpeg -i cracrypto.mp3 -ar 8000 -ac 1 -f mulaw /usr/share/asterisk/sounds/cracrypto.ulaw -y
   cp /usr/share/asterisk/sounds/cracrypto.ulaw /usr/share/asterisk/sounds/cracrypto.pcm
   
   # Convert thankyou
   ffmpeg -i thankyou.mp3 -ar 8000 -ac 1 -f mulaw /usr/share/asterisk/sounds/thankyou.ulaw -y
   cp /usr/share/asterisk/sounds/thankyou.ulaw /usr/share/asterisk/sounds/thankyou.pcm
   
   chmod 644 /usr/share/asterisk/sounds/cracrypto.* /usr/share/asterisk/sounds/thankyou.*
   ```

3. Reload Asterisk (if needed):
   ```bash
   asterisk -rx "core reload"
   ```

## Modified Files

1. **bot.py** - Removed TTS template selection, simplified campaign creation
2. **asterisk_config.py** - Updated dialplan to use cracrypto/thankyou audio files
3. **ami_listener.py** - Simplified to only notify on press 1
4. **generate_tts.py** - Converted to deploy pre-recorded audio instead of TTS

## Status

✅ All files uploaded to server
✅ Audio files converted and deployed
✅ Asterisk configuration updated
✅ System ready to use

## Next Steps

1. Start/restart the bot
2. Create a new campaign with `/newcampaign`
3. Upload phone list
4. Start campaign
5. Receive notifications when people press 1
