"""
SIP Account Management
Handles custom SIP, provider SIP, and Google Voice integration
"""
import requests
from typing import Dict, Optional
from config import Config
from database import SessionLocal, SIPAccount
import logging

logger = logging.getLogger(__name__)


class SIPManager:
    """Manage SIP accounts for users"""
    
    @staticmethod
    def add_custom_sip(user_id: int, name: str, sip_server: str, 
                       sip_username: str, sip_password: str, 
                       sip_port: int = 5060) -> SIPAccount:
        """
        Add custom SIP account
        
        Args:
            user_id: User's database ID
            name: Friendly name for the account
            sip_server: SIP server address
            sip_username: SIP username
            sip_password: SIP password
            sip_port: SIP port (default 5060)
        
        Returns:
            Created SIPAccount object
        """
        db = SessionLocal()
        try:
            sip_account = SIPAccount(
                user_id=user_id,
                name=name,
                provider_type='custom',
                sip_server=sip_server,
                sip_username=sip_username,
                sip_password=sip_password,
                sip_port=sip_port,
                is_active=True
            )
            db.add(sip_account)
            db.commit()
            db.refresh(sip_account)
            return sip_account
        finally:
            db.close()
    
    @staticmethod
    def add_google_voice(user_id: int, name: str, google_email: str, 
                        google_password: str, google_phone: str) -> SIPAccount:
        """
        Add Google Voice account
        
        Args:
            user_id: User's database ID
            name: Friendly name
            google_email: Google account email
            google_password: Google account password
            google_phone: Google Voice number
        
        Returns:
            Created SIPAccount object
        """
        db = SessionLocal()
        try:
            sip_account = SIPAccount(
                user_id=user_id,
                name=name,
                provider_type='google_voice',
                google_email=google_email,
                google_password=google_password,
                google_phone=google_phone,
                is_active=True
            )
            db.add(sip_account)
            db.commit()
            db.refresh(sip_account)
            return sip_account
        finally:
            db.close()
    
    @staticmethod
    def purchase_provider_sip(user_id: int, name: str, 
                             caller_id_number: str) -> Dict:
        """
        Purchase SIP account from provider
        
        Args:
            user_id: User's database ID
            name: Friendly name
            caller_id_number: Desired caller ID number
        
        Returns:
            Dict with purchase result
        """
        if not Config.SIP_PROVIDER_API_URL:
            return {
                'success': False,
                'error': 'SIP provider not configured'
            }
        
        try:
            # Call provider API to purchase SIP
            response = requests.post(
                f"{Config.SIP_PROVIDER_API_URL}/purchase",
                headers={
                    'Authorization': f'Bearer {Config.SIP_PROVIDER_API_KEY}'
                },
                json={
                    'caller_id': caller_id_number,
                    'user_id': user_id
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Save to database
                db = SessionLocal()
                try:
                    sip_account = SIPAccount(
                        user_id=user_id,
                        name=name,
                        provider_type='provider',
                        sip_server=data.get('sip_server'),
                        sip_username=data.get('sip_username'),
                        sip_password=data.get('sip_password'),
                        sip_port=data.get('sip_port', 5060),
                        caller_id_number=caller_id_number,
                        is_provider_sip=True,
                        provider_order_id=data.get('order_id'),
                        is_active=True
                    )
                    db.add(sip_account)
                    db.commit()
                    db.refresh(sip_account)
                    
                    return {
                        'success': True,
                        'account': sip_account,
                        'message': 'SIP account purchased successfully!'
                    }
                finally:
                    db.close()
            else:
                return {
                    'success': False,
                    'error': f'Purchase failed: {response.text}'
                }
                
        except Exception as e:
            logger.error(f"Error purchasing SIP: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_user_sip_accounts(user_id: int) -> list:
        """Get all SIP accounts for a user"""
        db = SessionLocal()
        try:
            return db.query(SIPAccount).filter(
                SIPAccount.user_id == user_id,
                SIPAccount.is_active == True
            ).all()
        finally:
            db.close()
    
    @staticmethod
    def update_sip_account(account_id: int, **kwargs) -> Optional[SIPAccount]:
        """Update SIP account details"""
        db = SessionLocal()
        try:
            account = db.query(SIPAccount).filter(
                SIPAccount.id == account_id
            ).first()
            
            if account:
                for key, value in kwargs.items():
                    if hasattr(account, key):
                        setattr(account, key, value)
                db.commit()
                db.refresh(account)
            
            return account
        finally:
            db.close()
    
    @staticmethod
    def delete_sip_account(account_id: int) -> bool:
        """Delete (deactivate) SIP account"""
        db = SessionLocal()
        try:
            account = db.query(SIPAccount).filter(
                SIPAccount.id == account_id
            ).first()
            
            if account:
                account.is_active = False
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    @staticmethod
    def configure_asterisk_sip(sip_account: SIPAccount) -> str:
        """
        Generate Asterisk SIP configuration
        
        Returns:
            SIP configuration string for pjsip.conf
        """
        if sip_account.provider_type == 'google_voice':
            # Google Voice uses Obihai/Motiv configuration
            return f"""
[{sip_account.name}]
type=endpoint
context=from-trunk
disallow=all
allow=ulaw
allow=alaw
direct_media=no
from_user={sip_account.google_phone}
outbound_auth={sip_account.name}-auth

[{sip_account.name}-auth]
type=auth
auth_type=userpass
username={sip_account.google_email}
password={sip_account.google_password}

[{sip_account.name}-reg]
type=registration
transport=transport-udp
outbound_auth={sip_account.name}-auth
server_uri=sip:gvgw.obihai.com
client_uri=sip:{sip_account.google_phone}@gvgw.obihai.com
"""
        else:
            # Standard SIP configuration
            return f"""
[{sip_account.name}]
type=endpoint
context=from-trunk
disallow=all
allow=ulaw
allow=alaw
outbound_auth={sip_account.name}-auth
aors={sip_account.name}

[{sip_account.name}-auth]
type=auth
auth_type=userpass
username={sip_account.sip_username}
password={sip_account.sip_password}

[{sip_account.name}]
type=aor
contact=sip:{sip_account.sip_username}@{sip_account.sip_server}:{sip_account.sip_port}

[{sip_account.name}-reg]
type=registration
transport=transport-udp
outbound_auth={sip_account.name}-auth
server_uri=sip:{sip_account.sip_server}:{sip_account.sip_port}
client_uri=sip:{sip_account.sip_username}@{sip_account.sip_server}
"""
    
    @staticmethod
    def test_sip_connection(sip_account: SIPAccount) -> Dict:
        """
        Test SIP connection
        
        Returns:
            Dict with test results
        """
        # TODO: Implement actual SIP connection test
        # For now, return success if credentials exist
        if sip_account.provider_type == 'google_voice':
            if sip_account.google_email and sip_account.google_password:
                return {'success': True, 'message': 'Google Voice credentials saved'}
        else:
            if sip_account.sip_server and sip_account.sip_username:
                return {'success': True, 'message': 'SIP credentials saved'}
        
        return {'success': False, 'message': 'Missing credentials'}
