"""
License Management System
Handles license generation, validation, and enforcement
"""
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from typing import Optional, Dict
import os


class LicenseManager:
    """
    Manages license key generation and validation
    """
    
    def __init__(self):
        """Initialize license manager with encryption key"""
        # Get or create encryption key
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _get_or_create_key(self) -> bytes:
        """Get existing key or create new one"""
        key_file = "license.key"
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
    
    def generate_license(
        self,
        user_id: Optional[int] = None,
        max_campaigns: int = 999,
        max_calls_per_day: int = 10000,
        expiry_days: int = 365
    ) -> str:
        """
        Generate a new license key
        
        Args:
            user_id: Telegram user ID (None for unassigned)
            max_campaigns: Maximum concurrent campaigns
            max_calls_per_day: Daily call limit
            expiry_days: License validity in days
        
        Returns:
            Encrypted license key string
        """
        # Calculate expiry date
        expiry = datetime.now() + timedelta(days=expiry_days)
        
        # Create license data
        license_data = {
            'user_id': user_id,
            'max_campaigns': max_campaigns,
            'max_calls_per_day': max_calls_per_day,
            'created_at': datetime.now().isoformat(),
            'expires_at': expiry.isoformat(),
            'nonce': secrets.token_hex(16)  # Unique identifier
        }
        
        # Encode and encrypt
        json_data = json.dumps(license_data)
        encrypted = self.cipher.encrypt(json_data.encode())
        
        # Create readable key format (groups of 4 chars)
        hex_key = encrypted.hex()
        formatted = '-'.join([hex_key[i:i+4] for i in range(0, min(len(hex_key), 20), 4)])
        
        return formatted.upper()
    
    def validate_license(self, license_key: str, user_id: int) -> Dict:
        """
        Validate a license key
        
        Args:
            license_key: License key to validate
            user_id: Telegram user ID attempting to use license
        
        Returns:
            Dict with validation result and license data
            {
                'valid': bool,
                'reason': str,
                'data': dict or None
            }
        """
        try:
            # Remove formatting
            clean_key = license_key.replace('-', '').replace(' ', '')
            
            # Convert back to bytes
            encrypted = bytes.fromhex(clean_key)
            
            # Decrypt
            decrypted = self.cipher.decrypt(encrypted)
            license_data = json.loads(decrypted.decode())
            
            # Check expiry
            expiry = datetime.fromisoformat(license_data['expires_at'])
            if datetime.now() > expiry:
                return {
                    'valid': False,
                    'reason': 'License expired',
                    'data': None
                }
            
            # Check user assignment
            if license_data['user_id'] is not None and license_data['user_id'] != user_id:
                return {
                    'valid': False,
                    'reason': 'License already assigned to another user',
                    'data': None
                }
            
            # Valid license
            return {
                'valid': True,
                'reason': 'License valid',
                'data': license_data
            }
            
        except Exception as e:
            return {
                'valid': False,
                'reason': f'Invalid license key format: {str(e)}',
                'data': None
            }
    
    def assign_license_to_user(self, license_key: str, user_id: int) -> bool:
        """
        Assign a license to a specific user (first use)
        
        Args:
            license_key: License key to assign
            user_id: Telegram user ID
        
        Returns:
            True if assignment successful
        """
        try:
            # Validate first
            result = self.validate_license(license_key, user_id)
            
            if not result['valid']:
                return False
            
            # If already assigned to this user, OK
            if result['data']['user_id'] == user_id:
                return True
            
            # If unassigned, assign it
            if result['data']['user_id'] is None:
                # Decrypt and update
                clean_key = license_key.replace('-', '').replace(' ', '')
                encrypted = bytes.fromhex(clean_key)
                decrypted = self.cipher.decrypt(encrypted)
                license_data = json.loads(decrypted.decode())
                
                # Update user_id
                license_data['user_id'] = user_id
                license_data['assigned_at'] = datetime.now().isoformat()
                
                # Re-encrypt and save
                json_data = json.dumps(license_data)
                new_encrypted = self.cipher.encrypt(json_data.encode())
                
                # Note: In production, store this mapping in database
                # For now, just validate that assignment would work
                return True
            
            return False
            
        except Exception:
            return False
    
    def get_license_info(self, license_key: str) -> Optional[Dict]:
        """
        Get license information without validation
        
        Args:
            license_key: License key
        
        Returns:
            License data dict or None
        """
        try:
            clean_key = license_key.replace('-', '').replace(' ', '')
            encrypted = bytes.fromhex(clean_key)
            decrypted = self.cipher.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception:
            return None
    
    def check_feature_allowed(
        self,
        license_data: Dict,
        feature: str,
        current_usage: int = 0
    ) -> bool:
        """
        Check if a feature is allowed under license
        
        Args:
            license_data: Decrypted license data
            feature: Feature to check ('campaigns' or 'calls')
            current_usage: Current usage count
        
        Returns:
            True if feature is allowed
        """
        if feature == 'campaigns':
            return current_usage < license_data.get('max_campaigns', 0)
        
        elif feature == 'calls':
            return current_usage < license_data.get('max_calls_per_day', 0)
        
        return False
    
    def get_license_limits(self, license_data: Dict) -> Dict:
        """
        Get all license limits
        
        Args:
            license_data: Decrypted license data
        
        Returns:
            Dict with limits
        """
        return {
            'max_campaigns': license_data.get('max_campaigns', 0),
            'max_calls_per_day': license_data.get('max_calls_per_day', 0),
            'expires_at': license_data.get('expires_at'),
            'days_remaining': self._get_days_remaining(license_data)
        }
    
    def _get_days_remaining(self, license_data: Dict) -> int:
        """Calculate days remaining until expiry"""
        try:
            expiry = datetime.fromisoformat(license_data['expires_at'])
            delta = expiry - datetime.now()
            return max(0, delta.days)
        except Exception:
            return 0
    
    def generate_test_license(self, days: int = 7) -> str:
        """
        Generate a test/trial license
        
        Args:
            days: Trial period in days
        
        Returns:
            License key for trial
        """
        return self.generate_license(
            user_id=None,
            max_campaigns=3,
            max_calls_per_day=100,
            expiry_days=days
        )
    
    def generate_premium_license(self, years: int = 1) -> str:
        """
        Generate a premium/unlimited license
        
        Args:
            years: License validity in years
        
        Returns:
            License key for premium
        """
        return self.generate_license(
            user_id=None,
            max_campaigns=999,
            max_calls_per_day=100000,
            expiry_days=years * 365
        )
    
    def batch_generate_licenses(
        self,
        count: int,
        license_type: str = 'standard'
    ) -> list:
        """
        Generate multiple licenses at once
        
        Args:
            count: Number of licenses to generate
            license_type: 'trial', 'standard', or 'premium'
        
        Returns:
            List of license keys
        """
        licenses = []
        
        for _ in range(count):
            if license_type == 'trial':
                key = self.generate_test_license()
            elif license_type == 'premium':
                key = self.generate_premium_license()
            else:  # standard
                key = self.generate_license()
            
            licenses.append(key)
        
        return licenses


# Command-line interface for license generation
if __name__ == '__main__':
    import sys
    
    lm = LicenseManager()
    
    print("=" * 60)
    print("  AutoDialer Pro - License Generator")
    print("=" * 60)
    print()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'trial':
            # Generate trial license
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            key = lm.generate_test_license(days)
            print(f"🎫 Trial License ({days} days):")
            print(f"   {key}")
            print()
            
        elif command == 'standard':
            # Generate standard license
            years = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            key = lm.generate_license(expiry_days=years * 365)
            print(f"🎫 Standard License ({years} year):")
            print(f"   {key}")
            print()
            
        elif command == 'premium':
            # Generate premium license
            years = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            key = lm.generate_premium_license(years)
            print(f"🎫 Premium License ({years} year):")
            print(f"   {key}")
            print()
            
        elif command == 'batch':
            # Generate multiple licenses
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            license_type = sys.argv[3] if len(sys.argv) > 3 else 'standard'
            
            print(f"Generating {count} {license_type} licenses...")
            print()
            
            licenses = lm.batch_generate_licenses(count, license_type)
            for i, key in enumerate(licenses, 1):
                print(f"{i:3d}. {key}")
            
            # Save to file
            filename = f"licenses_{license_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                for key in licenses:
                    f.write(key + '\n')
            
            print()
            print(f"✅ Saved to {filename}")
            print()
            
        elif command == 'validate':
            # Validate a license
            if len(sys.argv) < 3:
                print("Usage: python license_manager.py validate <license-key> [user-id]")
                sys.exit(1)
            
            key = sys.argv[2]
            user_id = int(sys.argv[3]) if len(sys.argv) > 3 else 123456789
            
            result = lm.validate_license(key, user_id)
            
            if result['valid']:
                print("✅ License Valid!")
                print()
                info = lm.get_license_info(key)
                limits = lm.get_license_limits(info)
                print(f"   Max Campaigns:    {limits['max_campaigns']}")
                print(f"   Max Calls/Day:    {limits['max_calls_per_day']}")
                print(f"   Days Remaining:   {limits['days_remaining']}")
                print(f"   Expires:          {limits['expires_at']}")
            else:
                print(f"❌ License Invalid: {result['reason']}")
            
            print()
        
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    
    else:
        # Interactive mode
        print("Select license type:")
        print("  1. Trial (7 days, 3 campaigns, 100 calls/day)")
        print("  2. Standard (1 year, unlimited campaigns, 10k calls/day)")
        print("  3. Premium (1 year, unlimited campaigns, 100k calls/day)")
        print("  4. Custom")
        print()
        
        choice = input("Enter choice (1-4): ").strip()
        
        if choice == '1':
            days = input("Trial days [7]: ").strip() or '7'
            key = lm.generate_test_license(int(days))
        
        elif choice == '2':
            years = input("Years [1]: ").strip() or '1'
            key = lm.generate_license(expiry_days=int(years) * 365)
        
        elif choice == '3':
            years = input("Years [1]: ").strip() or '1'
            key = lm.generate_premium_license(int(years))
        
        elif choice == '4':
            print()
            max_campaigns = int(input("Max campaigns [999]: ").strip() or '999')
            max_calls = int(input("Max calls/day [10000]: ").strip() or '10000')
            days = int(input("Valid for days [365]: ").strip() or '365')
            
            key = lm.generate_license(
                max_campaigns=max_campaigns,
                max_calls_per_day=max_calls,
                expiry_days=days
            )
        
        else:
            print("Invalid choice")
            sys.exit(1)
        
        print()
        print("=" * 60)
        print("🎫 LICENSE KEY:")
        print()
        print(f"   {key}")
        print()
        print("=" * 60)
        print()
        print("Give this key to your customer.")
        print("They will enter it in the Telegram bot.")
        print()
    
    print("Usage examples:")
    print("  python license_manager.py trial 14")
    print("  python license_manager.py standard 1")
    print("  python license_manager.py premium 2")
    print("  python license_manager.py batch 10 standard")
    print("  python license_manager.py validate <key> <user-id>")
    print()
