from fastapi import APIRouter, Depends, status
from app.core.dependencies import get_current_user, get_bearer_token
from app.models.user_model import User
from app.schemas.user_schema import (
    UserRegister, UserLogin, UserTokenResponse, 
    RefreshTokenRequest, LogoutRequest, UserResponse
)
from app.schemas.email_otp_schema import (
    ForgotPasswordRequest, ResetPasswordRequest, 
    VerifyOTPRequest, ResendOTPRequest
)
from app.schemas.common_schema import ApiResponse
from app.services.user_services import UserServices
from app.utils.responses import success_response

router = APIRouter()

@router.post("/register", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserRegister):
    created_user = await UserServices.user_registration(user_in)
    return success_response("User registered successfully", created_user)

@router.post("/login", response_model=ApiResponse[UserTokenResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def login_user(user_in: UserLogin):
    token_response = await UserServices.login_and_issue_tokens(user_in.email, user_in.password)
    return success_response("User logged in successfully", token_response)

@router.post("/refresh", response_model=ApiResponse[UserTokenResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def refresh_token(token_in: RefreshTokenRequest):
    token_response = await UserServices.refresh_user_token(token_in)
    return success_response("Token refreshed successfully", token_response)

@router.post("/logout", response_model=ApiResponse[None], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def logout_user(
    logout_in: LogoutRequest,
    current_user: User = Depends(get_current_user),
    access_token: str = Depends(get_bearer_token),
):
    await UserServices.logout_user(current_user, access_token, logout_in)
    return success_response("User logged out successfully")

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
    await UserServices.forgot_password_request(data)
    return success_response("If an account is associated with this email, a reset code has been sent.")

@router.post("/reset-password", response_model=ApiResponse[None])
async def reset_password(data: ResetPasswordRequest):
    await UserServices.reset_password_with_otp(data)
    return success_response("Your password has been reset successfully. You can now login with your new password.")