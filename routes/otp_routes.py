from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from utils.email_service import send_otp_email
from utils.otp_manager import generate_otp, store_otp, verify_otp, delete_otp, get_otp_info
from models.database import get_db_connection

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
async def send_otp(request: SendOTPRequest):
    """
    Send OTP to user's email
    Purpose can be: verification, password_reset, login
    """
    try:
        # Check if user exists in database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM users WHERE email = ?", (request.email,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found with this email")
        
        user_id, user_name = user
        
        # Generate OTP
        otp_code = generate_otp(6)
        
        # Store OTP
        store_otp(request.email, otp_code, request.purpose, expires_in_minutes=10)
        
        # Send email
        send_otp_email(request.email, otp_code, user_name)
        
        return OTPResponse(
            success=True,
            message="OTP sent successfully to your email",
            data={
                "email": request.email,
                "expires_in": "10 minutes"
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
        # Verify OTP
        is_valid, message = verify_otp(request.email, request.otp, request.purpose)
        
        if not is_valid:
            return OTPResponse(
                success=False,
                message=message
            )
        
        return OTPResponse(
            success=True,
            message="OTP verified successfully",
            data={
                "email": request.email,
                "verified": True
            }
        )
        
    except Exception as e:
        print(f"❌ Error verifying OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify OTP: {str(e)}")


@router.post("/resend", response_model=OTPResponse)
async def resend_otp(request: SendOTPRequest):
    """
    Resend OTP to user's email
    """
    try:
        # Delete old OTP if exists
        delete_otp(request.email)
        
        # Use the send_otp endpoint
        return await send_otp(request)
        
    except Exception as e:
        print(f"❌ Error resending OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resend OTP: {str(e)}")


@router.delete("/cancel/{email}")
async def cancel_otp(email: str):
    """
    Cancel/delete OTP for an email
    """
    try:
        deleted = delete_otp(email)
        
        if deleted:
            return OTPResponse(
                success=True,
                message="OTP cancelled successfully"
            )
        else:
            return OTPResponse(
                success=False,
                message="No OTP found for this email"
            )
            
    except Exception as e:
        print(f"❌ Error cancelling OTP: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Debug endpoint (remove in production)
@router.get("/debug/{email}")
async def get_otp_debug_info(email: str):
    """
    Get OTP information for debugging (REMOVE IN PRODUCTION!)
    """
    info = get_otp_info(email)
    
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