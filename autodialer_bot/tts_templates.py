"""
Pre-made TTS Templates
"""

TTS_TEMPLATES = {
    "CRA": {
        "name": "🇨🇦 CRA - Tax Verification",
        "message": "Hello, this is an important message from the Canada Revenue Agency. We need to verify your tax information. Press 1 to speak with an agent, or press 2 for a callback."
    },
    "NDAX": {
        "name": "💰 NDAX - Account Verification",
        "message": "Hello, this is a message from NDAX regarding your crypto account. Please press 1 to speak with our verification team, or press 2 to request a callback."
    },
    "BANK": {
        "name": "🏦 Bank - Security Alert",
        "message": "This is an urgent security alert from your bank. We have detected unusual activity on your account. Press 1 to speak with our fraud department immediately, or press 2 for a callback."
    },
    "PRIZE": {
        "name": "🎁 Prize Winner Notification",
        "message": "Congratulations! You have been selected as a winner in our recent promotion. Press 1 to claim your prize now, or press 2 to schedule a callback."
    },
    "SUPPORT": {
        "name": "🛠️ Technical Support",
        "message": "Hello, this is technical support calling about your recent service inquiry. Press 1 to speak with a technician now, or press 2 for a callback."
    },
    "CUSTOM": {
        "name": "✏️ Custom Message",
        "message": ""  # Will be filled by user
    }
}

def get_template_keyboard():
    """Get inline keyboard with TTS template options"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = []
    for key, template in TTS_TEMPLATES.items():
        if key != "CUSTOM":
            keyboard.append([InlineKeyboardButton(template["name"], callback_data=f"tts_{key}")])
    
    # Add custom option at the end
    keyboard.append([InlineKeyboardButton(TTS_TEMPLATES["CUSTOM"]["name"], callback_data="tts_CUSTOM")])
    
    return InlineKeyboardMarkup(keyboard)

def get_template_message(template_key: str) -> str:
    """Get the TTS message for a template"""
    return TTS_TEMPLATES.get(template_key, {}).get("message", "")
