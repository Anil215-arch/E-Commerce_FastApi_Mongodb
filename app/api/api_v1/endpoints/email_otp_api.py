from fastapi import APIRouter
from app.schemas.common_schema import ApiResponse
from app.schemas.email_otp_schema import ForgotPasswordRequest, ResetPasswordRequest, VerifyOTPRequest, ResendOTPRequest
from app.services.user_services import UserServices 
from app.utils.responses import success_response 

router = APIRouter()


@router.post("/verify-registration")
async def verify_registration(data: VerifyOTPRequest):
    message = await UserServices.verify_email_registration(data)
    return success_response(message)

@router.post("/resend-otp")
async def resend_otp(data: ResendOTPRequest):
    await UserServices.resend_verification_otp(data.email)
    return success_response("A new OTP has been sent to your email.")


@router.post("/forgot-password", response_model=ApiResponse[None])
async def forgot_password_request(data: ForgotPasswordRequest):
    """
    Public endpoint to request a password reset OTP.
    """
    await UserServices.forgot_password_request(data)
    
    # We provide a vague but helpful message to the user.
    return success_response("If an account is associated with this email, a reset code has been sent.")


@router.post("/reset-password", response_model=ApiResponse[None])
async def reset_password(data: ResetPasswordRequest):
    """
    Public endpoint to reset password using a verified OTP.
    """
    await UserServices.reset_password_with_otp(data)
    
    return success_response("Your password has been reset successfully. You can now login with your new password.")