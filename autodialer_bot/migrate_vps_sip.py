#!/usr/bin/env python3
"""
Database migration: Add SIP fields to VPSServer table
"""

from sqlalchemy import text
from database import engine, SessionLocal

def migrate():
    """Add SIP columns to vps_servers table"""
    
    migrations = [
        # SIP Configuration
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS sip_type VARCHAR(50) DEFAULT 'sip'",
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS sip_server VARCHAR(255)",
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS sip_username VARCHAR(255)",
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS sip_password VARCHAR(255)",
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS sip_port INTEGER DEFAULT 5060",
        
        # Google Voice Configuration
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS google_email VARCHAR(255)",
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS google_password VARCHAR(255)",
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS google_phone VARCHAR(20)",
        
        # Caller ID
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS caller_id_name VARCHAR(255)",
        "ALTER TABLE vps_servers ADD COLUMN IF NOT EXISTS caller_id_number VARCHAR(20)",
    ]
    
    with engine.connect() as conn:
        for migration in migrations:
            try:
                print(f"Executing: {migration}")
                conn.execute(text(migration))
                conn.commit()
                print("✅ Success")
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
    
    print("\n🎉 Migration complete!")

if __name__ == "__main__":
    migrate()
