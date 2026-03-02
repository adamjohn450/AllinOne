#!/usr/bin/env python3
"""
License Manager for AutoDialer Bot
Simple UUID-based license system with database storage
"""

import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from database import SessionLocal, License
from sqlalchemy.exc import IntegrityError


class LicenseManager:
    """
    Manages license key generation and validation
    Keys format: P{plan}-{segment1}-{segment2}-{segment3}
    Example: P1-A3F5-B7C9-E2D4
    """
    
    PLAN_TYPES = {
        1: {'name': 'Standard', 'max_campaigns': 999, 'max_calls': 10000},
        2: {'name': 'Premium', 'max_campaigns': 9999, 'max_calls': 100000},
        3: {'name': 'Trial', 'max_campaigns': 3, 'max_calls': 100}
    }
    
    def generate_license(
        self,
        plan_type: int = 1,
        max_campaigns: Optional[int] = None,
        max_calls_per_day: Optional[int] = None,
        expiry_days: int = 365,
        user_id: Optional[int] = None
    ) -> str:
        """
        Generate a new license key
        
        Args:
            plan_type: 1=Standard, 2=Premium, 3=Trial
            max_campaigns: Override default max campaigns
            max_calls_per_day: Override default max calls
            expiry_days: Days until expiration
            user_id: Optional pre-assignment to user
        
        Returns:
            License key in format P1-XXXX-XXXX-XXXX
        """
        # Get plan defaults
        plan = self.PLAN_TYPES.get(plan_type, self.PLAN_TYPES[1])
        
        if max_campaigns is None:
            max_campaigns = plan['max_campaigns']
        if max_calls_per_day is None:
            max_calls_per_day = plan['max_calls']
        
        # Generate unique key
        while True:
            # Generate 3 segments of 4 hex chars each
            segments = [secrets.token_hex(2).upper() for _ in range(3)]
            key = f"P{plan_type}-{'-'.join(segments)}"
            
            # Check if key already exists
            db = SessionLocal()
            try:
                existing = db.query(License).filter_by(key=key).first()
                if not existing:
                    break
            finally:
                db.close()
        
        # Create license in database
        db = SessionLocal()
        try:
            license_obj = License(
                key=key,
                plan_type=plan_type,
                max_campaigns=max_campaigns,
                max_calls_per_day=max_calls_per_day,
                expires_at=datetime.utcnow() + timedelta(days=expiry_days),
                assigned_user_id=user_id,
                assigned_at=datetime.utcnow() if user_id else None
            )
            db.add(license_obj)
            db.commit()
            return key
        except IntegrityError:
            db.rollback()
            # Key collision (very unlikely), retry
            return self.generate_license(plan_type, max_campaigns, max_calls_per_day, expiry_days, user_id)
        finally:
            db.close()
    
    def validate_license(self, license_key: str, user_id: int) -> Dict:
        """
        Validate a license key
        
        Args:
            license_key: License key to validate
            user_id: Telegram user ID attempting to use
        
        Returns:
            {
                'valid': bool,
                'reason': str,
                'data': License object or None
            }
        """
        db = SessionLocal()
        try:
            # Clean key
            clean_key = license_key.strip().upper().replace(' ', '')
            
            # Find license
            license_obj = db.query(License).filter_by(key=clean_key).first()
            
            if not license_obj:
                return {
                    'valid': False,
                    'reason': 'License key not found',
                    'data': None
                }
            
            # Check if active
            if not license_obj.is_active:
                return {
                    'valid': False,
                    'reason': 'License has been deactivated',
                    'data': None
                }
            
            # Check expiry
            if datetime.utcnow() > license_obj.expires_at:
                return {
                    'valid': False,
                    'reason': 'License expired',
                    'data': None
                }
            
            # Check if already assigned to different user
            if license_obj.assigned_user_id and license_obj.assigned_user_id != user_id:
                return {
                    'valid': False,
                    'reason': 'License already assigned to another user',
                    'data': None
                }
            
            # Valid!
            return {
                'valid': True,
                'reason': 'Valid',
                'data': license_obj
            }
        
        finally:
            db.close()
    
    def assign_license_to_user(self, license_key: str, user_id: int) -> bool:
        """
        Assign a license to a user
        
        Args:
            license_key: License key
            user_id: Telegram user ID
        
        Returns:
            True if successful
        """
        db = SessionLocal()
        try:
            clean_key = license_key.strip().upper().replace(' ', '')
            license_obj = db.query(License).filter_by(key=clean_key).first()
            
            if not license_obj:
                return False
            
            # Assign if not already assigned
            if not license_obj.assigned_user_id:
                license_obj.assigned_user_id = user_id
                license_obj.assigned_at = datetime.utcnow()
                db.commit()
            
            return True
        
        finally:
            db.close()
    
    def get_license_info(self, license_key: str) -> Optional[License]:
        """
        Get license information
        
        Args:
            license_key: License key
        
        Returns:
            License object or None
        """
        db = SessionLocal()
        try:
            clean_key = license_key.strip().upper().replace(' ', '')
            return db.query(License).filter_by(key=clean_key).first()
        finally:
            db.close()
    
    def get_license_limits(self, license_obj: License) -> Dict:
        """
        Get license limits
        
        Args:
            license_obj: License database object
        
        Returns:
            Dict with limits
        """
        if not license_obj:
            return {
                'max_campaigns': 0,
                'max_calls_per_day': 0,
                'days_remaining': 0,
                'expires_at': None
            }
        
        days_remaining = (license_obj.expires_at - datetime.utcnow()).days
        
        return {
            'max_campaigns': license_obj.max_campaigns,
            'max_calls_per_day': license_obj.max_calls_per_day,
            'days_remaining': max(0, days_remaining),
            'expires_at': license_obj.expires_at
        }
    
    def generate_test_license(self, days: int = 7) -> str:
        """Generate trial license"""
        return self.generate_license(
            plan_type=3,
            expiry_days=days
        )
    
    def generate_premium_license(self, years: int = 1) -> str:
        """Generate premium license"""
        return self.generate_license(
            plan_type=2,
            expiry_days=years * 365
        )
    
    def batch_generate_licenses(
        self,
        count: int,
        license_type: str = 'standard'
    ) -> List[str]:
        """
        Generate multiple licenses
        
        Args:
            count: Number of licenses
            license_type: 'trial', 'standard', or 'premium'
        
        Returns:
            List of license keys
        """
        plan_map = {
            'trial': 3,
            'standard': 1,
            'premium': 2
        }
        
        plan_type = plan_map.get(license_type.lower(), 1)
        licenses = []
        
        for _ in range(count):
            key = self.generate_license(plan_type=plan_type)
            licenses.append(key)
        
        return licenses


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
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            key = lm.generate_test_license(days)
            print(f"🎫 Trial License ({days} days):")
            print(f"   {key}")
            print()
            
        elif command == 'standard':
            years = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            key = lm.generate_license(plan_type=1, expiry_days=years * 365)
            print(f"🎫 Standard License ({years} year):")
            print(f"   {key}")
            print()
            
        elif command == 'premium':
            years = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            key = lm.generate_premium_license(years)
            print(f"🎫 Premium License ({years} year):")
            print(f"   {key}")
            print()
            
        elif command == 'batch':
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
            if len(sys.argv) < 3:
                print("Usage: python license_manager.py validate <license-key> [user-id]")
                sys.exit(1)
            
            key = sys.argv[2]
            user_id = int(sys.argv[3]) if len(sys.argv) > 3 else 123456789
            
            result = lm.validate_license(key, user_id)
            
            if result['valid']:
                print("✅ License Valid!")
                print()
                license_obj = result['data']
                limits = lm.get_license_limits(license_obj)
                plan_name = lm.PLAN_TYPES.get(license_obj.plan_type, {}).get('name', 'Unknown')
                print(f"   Plan:             {plan_name}")
                print(f"   Max Campaigns:    {limits['max_campaigns']}")
                print(f"   Max Calls/Day:    {limits['max_calls_per_day']}")
                print(f"   Days Remaining:   {limits['days_remaining']}")
                print(f"   Expires:          {limits['expires_at']}")
                print(f"   Assigned:         {'Yes' if license_obj.assigned_user_id else 'No'}")
            else:
                print(f"❌ License Invalid: {result['reason']}")
            
            print()
        
        else:
            print(f"Unknown command: {command}")
            print()
            print("Usage:")
            print("  python license_manager.py trial [days]")
            print("  python license_manager.py standard [years]")
            print("  python license_manager.py premium [years]")
            print("  python license_manager.py batch <count> <type>")
            print("  python license_manager.py validate <key> [user-id]")
            sys.exit(1)
    
    else:
        # Interactive mode
        print("Select license type:")
        print("  1. Trial (7 days, 3 campaigns, 100 calls/day)")
        print("  2. Standard (1 year, 999 campaigns, 10k calls/day)")
        print("  3. Premium (1 year, 9999 campaigns, 100k calls/day)")
        print()
        
        choice = input("Enter choice (1-3): ").strip()
        
        if choice == '1':
            days = input("Trial days [7]: ").strip() or '7'
            key = lm.generate_test_license(int(days))
        
        elif choice == '2':
            years = input("Years [1]: ").strip() or '1'
            key = lm.generate_license(plan_type=1, expiry_days=int(years) * 365)
        
        elif choice == '3':
            years = input("Years [1]: ").strip() or '1'
            key = lm.generate_premium_license(int(years))
        
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
