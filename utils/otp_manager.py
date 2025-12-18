import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict
import hashlib
from sqlalchemy.orm import Session
from models.database import OTP, SessionLocal

def generate_otp(length: int = 6) -> str:
    """
    Generate a random OTP code.
    
    Args:
        length: Length of the OTP (default: 6)
    
    Returns:
        str: Generated OTP code
    """
    return ''.join(random.choices(string.digits, k=length))

def store_otp(email: str, otp: str, expiry_minutes: int = 10, purpose: str = "verification") -> bool:
    """
    Store OTP in database with expiration time.
    
    Args:
        email: User's email address
        otp: OTP code to store
        expiry_minutes: Minutes until OTP expires (default: 10)
        purpose: Purpose of OTP (verification, password_reset, login)
    
    Returns:
        bool: True if stored successfully
    """
    db = SessionLocal()
    try:
        # Hash the OTP for security
        hashed_otp = hashlib.sha256(otp.encode()).hexdigest()
        
        # Delete any existing OTPs for this email and purpose
        db.query(OTP).filter(
            OTP.email == email,
            OTP.purpose == purpose
        ).delete()
        
        # Create new OTP record
        expiry_time = datetime.utcnow() + timedelta(minutes=expiry_minutes)
        
        new_otp = OTP(
            email=email,
            otp_hash=hashed_otp,
            purpose=purpose,
            expires_at=expiry_time,
            attempts=0,
            is_used=False
        )
        
        db.add(new_otp)
        db.commit()
        
        return True
    except Exception as e:
        db.rollback()
        print(f"Error storing OTP: {e}")
        return False
    finally:
        db.close()

def verify_otp(email: str, otp: str, max_attempts: int = 3, purpose: str = "verification") -> bool:
    """
    Verify OTP code for a given email.
    
    Args:
        email: User's email address
        otp: OTP code to verify
        max_attempts: Maximum verification attempts allowed (default: 3)
        purpose: Purpose of OTP to verify
    
    Returns:
        bool: True if OTP is valid and not expired
    """
    db = SessionLocal()
    try:
        # Find the OTP record
        otp_record = db.query(OTP).filter(
            OTP.email == email,
            OTP.purpose == purpose,
            OTP.is_used == False
        ).first()
        
        if not otp_record:
            return False
        
        # Check if max attempts exceeded
        if otp_record.attempts >= max_attempts:
            db.delete(otp_record)
            db.commit()
            return False
        
        # Increment attempts
        otp_record.attempts += 1
        db.commit()
        
        # Check if OTP expired
        if datetime.utcnow() > otp_record.expires_at:
            db.delete(otp_record)
            db.commit()
            return False
        
        # Verify OTP
        hashed_input = hashlib.sha256(otp.encode()).hexdigest()
        
        if hashed_input == otp_record.otp_hash:
            # Mark as used and delete
            db.delete(otp_record)
            db.commit()
            return True
        
        return False
        
    except Exception as e:
        db.rollback()
        print(f"Error verifying OTP: {e}")
        return False
    finally:
        db.close()

def delete_otp(email: str, purpose: str = None) -> bool:
    """
    Delete OTP for a given email.
    
    Args:
        email: User's email address
        purpose: Optional purpose filter
    
    Returns:
        bool: True if deleted successfully
    """
    db = SessionLocal()
    try:
        query = db.query(OTP).filter(OTP.email == email)
        
        if purpose:
            query = query.filter(OTP.purpose == purpose)
        
        deleted_count = query.delete()
        db.commit()
        
        return deleted_count > 0
    except Exception as e:
        db.rollback()
        print(f"Error deleting OTP: {e}")
        return False
    finally:
        db.close()

def get_otp_info(email: str, purpose: str = None) -> Optional[Dict]:
    """
    Get OTP information for a given email (for debugging/admin purposes).
    
    Args:
        email: User's email address
        purpose: Optional purpose filter
    
    Returns:
        Optional[Dict]: OTP info if exists, None otherwise
    """
    db = SessionLocal()
    try:
        query = db.query(OTP).filter(OTP.email == email)
        
        if purpose:
            query = query.filter(OTP.purpose == purpose)
        
        otp_record = query.first()
        
        if not otp_record:
            return None
        
        return {
            'email': otp_record.email,
            'purpose': otp_record.purpose,
            'expiry': otp_record.expires_at.isoformat(),
            'attempts': otp_record.attempts,
            'is_expired': datetime.utcnow() > otp_record.expires_at,
            'is_used': otp_record.is_used,
            'created_at': otp_record.created_at.isoformat()
        }
    except Exception as e:
        print(f"Error getting OTP info: {e}")
        return None
    finally:
        db.close()

def cleanup_expired_otps() -> int:
    """
    Remove all expired OTPs from database.
    Should be run periodically (e.g., via cron job or scheduler).
    
    Returns:
        int: Number of OTPs cleaned up
    """
    db = SessionLocal()
    try:
        count = db.query(OTP).filter(
            OTP.expires_at < datetime.utcnow()
        ).delete()
        
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        print(f"Error cleaning up expired OTPs: {e}")
        return 0
    finally:
        db.close()