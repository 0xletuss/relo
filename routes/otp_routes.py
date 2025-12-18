from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from utils.email_service import send_otp_email
from utils.otp_manager import generate_otp, store_otp, verify_otp, delete_otp, get_otp_info
from models.database import get_db, User

router = APIRouter()

# Request/Response Models
class SendOTPRequest(BaseModel):
    email: EmailStr
    purpose: str = "verification"  # verification, password_reset, login

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    purpose: str = "verification"

class OTPResponse(BaseModel):
    success: bool
    message: str
    data: dict = None


@router.post("/send", response_model=OTPResponse)
async def send_otp(request: SendOTPRequest, db: Session = Depends(get_db)):
    """
    Send OTP to user's email
    Purpose can be: verification, password_reset, login
    """
    try:
        # Check if user exists in database
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found with this email")
        
        # Generate OTP
        otp_code = generate_otp(6)
        
        # Store OTP with 10 minutes expiry
        if not store_otp(request.email, otp_code, expiry_minutes=10, purpose=request.purpose):
            raise HTTPException(status_code=500, detail="Failed to store OTP")
        
        # Send email
        user_name = user.username or "User"
        send_otp_email(request.email, otp_code, user_name)
        
        return OTPResponse(
            success=True,
            message="OTP sent successfully to your email",
            data={
                "email": request.email,
                "expires_in": "10 minutes",
                "purpose": request.purpose
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error sending OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")


@router.post("/verify", response_model=OTPResponse)
async def verify_otp_code(request: VerifyOTPRequest):
    """
    Verify OTP code
    """
    try:
        # Verify OTP (returns True/False)
        is_valid = verify_otp(request.email, request.otp, max_attempts=3, purpose=request.purpose)
        
        if not is_valid:
            return OTPResponse(
                success=False,
                message="Invalid or expired OTP. Please request a new one."
            )
        
        return OTPResponse(
            success=True,
            message="OTP verified successfully",
            data={
                "email": request.email,
                "verified": True,
                "purpose": request.purpose
            }
        )
        
    except Exception as e:
        print(f"❌ Error verifying OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify OTP: {str(e)}")


@router.post("/resend", response_model=OTPResponse)
async def resend_otp(request: SendOTPRequest, db: Session = Depends(get_db)):
    """
    Resend OTP to user's email
    """
    try:
        # Delete old OTP if exists
        delete_otp(request.email, purpose=request.purpose)
        
        # Send new OTP
        return await send_otp(request, db)
        
    except Exception as e:
        print(f"❌ Error resending OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resend OTP: {str(e)}")


@router.delete("/cancel/{email}")
async def cancel_otp(email: str, purpose: str = None):
    """
    Cancel/delete OTP for an email
    Optional query parameter: purpose (verification, password_reset, login)
    """
    try:
        deleted = delete_otp(email, purpose=purpose)
        
        return OTPResponse(
            success=True,
            message="OTP cancelled successfully" if deleted else "No OTP found for this email"
        )
            
    except Exception as e:
        print(f"❌ Error cancelling OTP: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Debug endpoint (remove in production)
@router.get("/debug/{email}")
async def get_otp_debug_info(email: str, purpose: str = None):
    """
    Get OTP information for debugging (REMOVE IN PRODUCTION!)
    Optional query parameter: purpose
    """
    try:
        info = get_otp_info(email, purpose=purpose)
        
        if info:
            return {
                "success": True,
                "data": info
            }
        else:
            return {
                "success": False,
                "message": "No OTP found for this email"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }