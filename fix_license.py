#!/usr/bin/env python3
"""Fix license_manager.py: replace broken hex/truncation with direct Fernet token"""

with open('/root/autodialer_bot/license_manager.py', 'r') as f:
    src = f.read()

# Fix 1: generate_license - return full Fernet token instead of truncated hex
old_gen = '''        # Encode and encrypt
        json_data = json.dumps(license_data)
        encrypted = self.cipher.encrypt(json_data.encode())
        
        # Create readable key format (groups of 4 chars)
        hex_key = encrypted.hex()
        formatted = '-'.join([hex_key[i:i+4] for i in range(0, min(len(hex_key), 20), 4)])
        
        return formatted.upper()'''

new_gen = '''        # Encode and encrypt
        json_data = json.dumps(license_data)
        encrypted = self.cipher.encrypt(json_data.encode())  # returns base64url bytes
        
        # Return as readable string in groups of 10 chars
        token_str = encrypted.decode()
        formatted = '-'.join([token_str[i:i+10] for i in range(0, len(token_str), 10)])
        
        return formatted'''

if old_gen in src:
    src = src.replace(old_gen, new_gen)
    print('generate_license: fixed')
else:
    print('generate_license: NOT FOUND - checking alternatives')
    # check what's there
    import re
    m = re.search(r'hex_key.*?return.*?formatted', src, re.DOTALL)
    if m:
        print('Found:', repr(m.group(0)[:200]))

# Fix 2: validate_license - use .encode() instead of bytes.fromhex()
old_val = '''            # Convert back to bytes
            encrypted = bytes.fromhex(clean_key)
            
            # Decrypt
            decrypted = self.cipher.decrypt(encrypted)'''

new_val = '''            # Decrypt Fernet token (base64url string)
            decrypted = self.cipher.decrypt(clean_key.encode())'''

if old_val in src:
    src = src.replace(old_val, new_val)
    print('validate_license: fixed')
else:
    print('validate_license: NOT FOUND')

# Fix 3: assign_license_to_user - same fix
old_assign = '''            # If unassigned, assign it
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
                return True'''

new_assign = '''            # If unassigned, assign it
            if result['data']['user_id'] is None:
                # Just validate that assignment would work (user stored in DB)
                return True'''

if old_assign in src:
    src = src.replace(old_assign, new_assign)
    print('assign_license: fixed')
else:
    print('assign_license: NOT FOUND (may be OK)')

# Fix 4: get_license_info - same fix
old_get = '''            clean_key = license_key.replace('-', '').replace(' ', '')
            encrypted = bytes.fromhex(clean_key)
            decrypted = self.cipher.decrypt(encrypted)
            return json.loads(decrypted.decode())'''

new_get = '''            clean_key = license_key.replace('-', '').replace(' ', '')
            decrypted = self.cipher.decrypt(clean_key.encode())
            return json.loads(decrypted.decode())'''

if old_get in src:
    src = src.replace(old_get, new_get)
    print('get_license_info: fixed')
else:
    print('get_license_info: NOT FOUND')

with open('/root/autodialer_bot/license_manager.py', 'w') as f:
    f.write(src)

import subprocess, sys
r = subprocess.run([sys.executable, '-m', 'py_compile', '/root/autodialer_bot/license_manager.py'], capture_output=True, text=True)
if r.returncode == 0:
    print('license_manager.py: syntax OK')
else:
    print('SYNTAX ERROR:', r.stderr)

# Quick smoke test - generate and validate a key
print('\n=== Smoke test ===')
import sys
sys.path.insert(0, '/root/autodialer_bot')
from license_manager import LicenseManager
lm = LicenseManager()
key = lm.generate_license(user_id=None, max_campaigns=5, expiry_days=30)
print(f'Generated key (first 60 chars): {key[:60]}...')
print(f'Total key length: {len(key)}')
result = lm.validate_license(key, user_id=12345)
print(f'Validation result: valid={result["valid"]}, reason={result["reason"]}')
if result['valid']:
    print(f'Max campaigns: {result["data"]["max_campaigns"]}')
