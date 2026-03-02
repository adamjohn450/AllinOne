from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import Config

Base = declarative_base()

class User(Base):
    """User model"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    license_key = Column(String(255))
    license_valid_until = Column(DateTime)
    max_campaigns = Column(Integer, default=999)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    
    # VPS Settings
    vps_host = Column(String(255))
    vps_port = Column(Integer, default=5038)
    vps_ami_username = Column(String(255))
    vps_ami_password = Column(String(255))
    
    # Relationships
    campaigns = relationship('Campaign', back_populates='user', cascade='all, delete-orphan')
    servers = relationship('VPSServer', back_populates='user', cascade='all, delete-orphan')
    sip_accounts = relationship('SIPAccount', back_populates='user', cascade='all, delete-orphan')

class SIPAccount(Base):
    """SIP Account Configuration"""
    __tablename__ = 'sip_accounts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)  # Friendly name
    provider_type = Column(String(50), default='custom')  # custom, provider, google_voice
    
    # Custom SIP credentials
    sip_server = Column(String(255))
    sip_username = Column(String(255))
    sip_password = Column(String(255))
    sip_port = Column(Integer, default=5060)
    
    # Google Voice credentials
    google_email = Column(String(255))
    google_password = Column(String(255))
    google_phone = Column(String(20))
    
    # Caller ID (NOTE: Must be configured on SIP provider side)
    caller_id_name = Column(String(255))
    caller_id_number = Column(String(20))
    
    # Provider SIP (purchased from us)
    is_provider_sip = Column(Boolean, default=False)
    provider_order_id = Column(String(255))
    
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship('User', back_populates='sip_accounts')
    campaigns = relationship('Campaign', back_populates='sip_account')

class VPSServer(Base):
    """VPS Server configuration"""
    __tablename__ = 'vps_servers'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(255))
    host = Column(String(255), nullable=False)
    ssh_port = Column(Integer, default=22)
    ssh_username = Column(String(255))
    ssh_password = Column(String(255))
    ssh_key_path = Column(String(500))
    ami_port = Column(Integer, default=5038)
    ami_username = Column(String(255))
    ami_password = Column(String(255))
    
    # SIP Configuration (per VPS)
    sip_type = Column(String(50), default='sip')  # 'sip' or 'google_voice'
    sip_server = Column(String(255))
    sip_username = Column(String(255))
    sip_password = Column(String(255))
    sip_port = Column(Integer, default=5060)
    
    # Google Voice Configuration (alternative to SIP)
    google_email = Column(String(255))
    google_password = Column(String(255))
    google_phone = Column(String(20))
    
    # Caller ID
    caller_id_name = Column(String(255))
    caller_id_number = Column(String(20))
    
    is_active = Column(Boolean, default=True)
    asterisk_version = Column(String(50))
    status = Column(String(50), default='pending')  # pending, installing, ready, error
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship('User', back_populates='servers')

class Campaign(Base):
    """Campaign model"""
    __tablename__ = 'campaigns'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    server_id = Column(Integer, ForeignKey('vps_servers.id'))
    sip_account_id = Column(Integer, ForeignKey('sip_accounts.id'))
    name = Column(String(255), nullable=False)
    
    # Separate TTS for each option
    tts_transfer = Column(Text)  # TTS for option 1 (transfer)
    tts_callback = Column(Text)  # TTS for option 2 (callback)
    
    transfer_number = Column(String(20))
    hold_music_file = Column(String(500))
    max_concurrent = Column(Integer, default=10)
    status = Column(String(50), default='pending')  # pending, running, paused, completed, stopped
    
    # Detailed statistics
    total_numbers = Column(Integer, default=0)
    completed_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    no_answer_calls = Column(Integer, default=0)
    transferred_calls = Column(Integer, default=0)  # Press 1
    callback_requests = Column(Integer, default=0)  # Press 2
    active_calls = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    user = relationship('User', back_populates='campaigns')
    sip_account = relationship('SIPAccount', back_populates='campaigns')
    phone_numbers = relationship('PhoneNumber', back_populates='campaign', cascade='all, delete-orphan')
    call_logs = relationship('CallLog', back_populates='campaign')

class PhoneNumber(Base):
    """Phone numbers for campaigns"""
    __tablename__ = 'phone_numbers'
    
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    phone_number = Column(String(20), nullable=False)
    status = Column(String(50), default='pending')  # pending, calling, completed, failed, busy
    attempts = Column(Integer, default=0)
    last_attempt = Column(DateTime)
    
    campaign = relationship('Campaign', back_populates='phone_numbers')

class License(Base):
    """License keys"""
    __tablename__ = 'licenses'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    plan_type = Column(Integer, default=1)  # 1=standard, 2=premium, 3=trial
    max_campaigns = Column(Integer, default=999)
    max_calls_per_day = Column(Integer, default=10000)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    assigned_user_id = Column(BigInteger)  # Telegram user ID once assigned
    assigned_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    notes = Column(Text)

class CallLog(Base):
    """Call logs"""
    __tablename__ = 'call_logs'
    
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    phone_number = Column(String(20), nullable=False)
    status = Column(String(50))  # answered, no-answer, busy, failed, transferred, callback
    action_taken = Column(String(50))  # pressed_1, pressed_2, hung_up, no_action
    duration = Column(Integer, default=0)
    pressed_key = Column(String(5))
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
    
    campaign = relationship('Campaign', back_populates='call_logs')

# Database setup
engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
