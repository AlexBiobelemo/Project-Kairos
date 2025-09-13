"""
Standalone script to create test users
"""

import json
import hashlib
import secrets


def hash_password(password: str) -> str:
    """Hash password with salt"""
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', 
                                      password.encode('utf-8'), 
                                      salt.encode('utf-8'), 
                                      100000)
    return f"{salt}:{password_hash.hex()}"


def create_test_users():
    """Create test users file"""
    users = {
        "admin": {
            "password_hash": hash_password("SecureAdmin123!"),
            "role": "admin",
            "email": "admin@kairos.local"
        },
        "analyst": {
            "password_hash": hash_password("Analyst456!"),
            "role": "analyst",
            "email": "analyst@kairos.local"
        },
        "viewer": {
            "password_hash": hash_password("Viewer789!"),
            "role": "viewer",
            "email": "viewer@kairos.local"
        }
    }
    
    with open('users.json', 'w') as f:
        json.dump(users, f, indent=2)
    
    print("Test users created in users.json")
    print("Admin: admin / SecureAdmin123!")
    print("Analyst: analyst / Analyst456!")
    print("Viewer: viewer / Viewer789!")


if __name__ == "__main__":
    create_test_users()
