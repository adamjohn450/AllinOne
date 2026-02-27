import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # Telegram
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(',') if id.strip()]
    
    # Database - PostgreSQL for better performance
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://autodialer:autodialer@localhost/autodialer')
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # License
    LICENSE_SERVER_URL = os.getenv('LICENSE_SERVER_URL', '')
    MASTER_KEY_FILE = os.getenv('MASTER_KEY_FILE', 'master_key.bin')
    
    # SIP Provider (for selling SIP accounts to users)
    SIP_PROVIDER_API_URL = os.getenv('SIP_PROVIDER_API_URL', '')
    SIP_PROVIDER_API_KEY = os.getenv('SIP_PROVIDER_API_KEY', '')
    
    # Application
    MAX_CONCURRENT_CALLS = int(os.getenv('MAX_CONCURRENT_CALLS', 50))
    DEFAULT_MAX_CAMPAIGNS = int(os.getenv('DEFAULT_MAX_CAMPAIGNS', 999))
    
    # Feature Flags
    ENABLE_VPS_AUTO_SETUP = True
    ENABLE_VOICE_RECORDING = False
    ENABLE_CALL_RECORDING = False
    ENABLE_SIP_PURCHASE = True  # Allow users to buy SIP from us
    ENABLE_GOOGLE_VOICE = True  # Allow Google Voice integration
