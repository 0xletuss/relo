import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict
import hashlib

# In-memory storage for OTPs (for production, use Redis or database)
otp_storage: Dict[str, Dict] = {}

def generate_otp(length: int = 6) -> str:
    """
    Generate a random OTP code.
    
    Args:
        length: Length of the OTP (default: 6)
    
    Returns:
        str: Generated OTP code
    """
    return ''.join(random.choices(string.digits, k=length))

def store_otp(email: str, otp: str, expiry_minutes: int = 10) -> bool:
    """
    Store OTP with expiration time.
    
    Args:
        email: User's email address
        otp: OTP code to store
        expiry_minutes: Minutes until OTP expires (default: 10)
    
    Returns:
        bool: True if stored successfully
    """
    try:
        # Hash the OTP for security
        hashed_otp = hashlib.sha256(otp.encode()).hexdigest()
        
        expiry_time = datetime.now() + timedelta(minutes=expiry_minutes)
        
        otp_storage[email] = {
            'otp': hashed_otp,
            'expiry': expiry_time,
            'attempts': 0
        }
        
        return True
    except Exception as e:
        print(f"Error storing OTP: {e}")
        return False

def verify_otp(email: str, otp: str, max_attempts: int = 3) -> bool:
    """
    Verify OTP code for a given email.
    
    Args:
        email: User's email address
        otp: OTP code to verify
        max_attempts: Maximum verification attempts allowed (default: 3)
    
    Returns:
        bool: True if OTP is valid and not expired
    """
    if email not in otp_storage:
        return False
    
    stored_data = otp_storage[email]
    
    # Check if max attempts exceeded
    if stored_data['attempts'] >= max_attempts:
        delete_otp(email)
        return False
    
    # Increment attempts
    stored_data['attempts'] += 1
    
    # Check if OTP expired
    if datetime.now() > stored_data['expiry']:
        delete_otp(email)
        return False
    
    # Verify OTP
    hashed_input = hashlib.sha256(otp.encode()).hexdigest()
    
    if hashed_input == stored_data['otp']:
        # OTP is valid, delete it after successful verification
        delete_otp(email)
        return True
    
    return False

def delete_otp(email: str) -> bool:
    """
    Delete OTP for a given email.
    
    Args:
        email: User's email address
    
    Returns:
        bool: True if deleted successfully
    """
    try:
        if email in otp_storage:
            del otp_storage[email]
        return True
    except Exception as e:
        print(f"Error deleting OTP: {e}")
        return False

def get_otp_info(email: str) -> Optional[Dict]:
    """
    Get OTP information for a given email (for debugging/admin purposes).
    
    Args:
        email: User's email address
    
    Returns:
        Optional[Dict]: OTP info if exists, None otherwise
    """
    if email not in otp_storage:
        return None
    
    stored_data = otp_storage[email]
    
    return {
        'email': email,
        'expiry': stored_data['expiry'].isoformat(),
        'attempts': stored_data['attempts'],
        'is_expired': datetime.now() > stored_data['expiry']
    }

def cleanup_expired_otps() -> int:
    """
    Remove all expired OTPs from storage.
    
    Returns:
        int: Number of OTPs cleaned up
    """
    count = 0
    expired_emails = []
    
    for email, data in otp_storage.items():
        if datetime.now() > data['expiry']:
            expired_emails.append(email)
    
    for email in expired_emails:
        delete_otp(email)
        count += 1
    
    return count