from fastapi import APIRouter, Depends, Request, status
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
from app.core.rate_limiter import ip_key_func, limiter
from app.core.i18n import t
from app.core.message_keys import Msg

router = APIRouter()


@router.post("/register", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute", key_func=ip_key_func)
async def register_user(request: Request, user_in: UserRegister):
    created_user = await UserServices.user_registration(user_in)
    return success_response(t(request, Msg.USER_REGISTERED_SUCCESSFULLY), created_user)


@router.post("/login", response_model=ApiResponse[UserTokenResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute", key_func=ip_key_func)
async def login_user(request: Request, user_in: UserLogin):
    token_response = await UserServices.login_and_issue_tokens(user_in.email, user_in.password)
    return success_response(t(request, Msg.USER_LOGGED_IN_SUCCESSFULLY), token_response)


@router.post("/refresh", response_model=ApiResponse[UserTokenResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def refresh_token(request: Request, token_in: RefreshTokenRequest):
    token_response = await UserServices.refresh_user_token(token_in)
    return success_response(t(request, Msg.TOKEN_REFRESHED_SUCCESSFULLY), token_response)


@router.post("/logout", response_model=ApiResponse[None], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def logout_user(
    request: Request,
    logout_in: LogoutRequest,
    current_user: User = Depends(get_current_user),
    access_token: str = Depends(get_bearer_token),
):
    await UserServices.logout_user(current_user, access_token, logout_in)
    return success_response(t(request, Msg.USER_LOGGED_OUT_SUCCESSFULLY))


@router.post("/verify-registration")
@limiter.limit("10/minute", key_func=ip_key_func)
async def verify_registration(request: Request, data: VerifyOTPRequest):
    message = await UserServices.verify_email_registration(data)
    return success_response(t(request, message))


@router.post("/resend-otp")
@limiter.limit("3/minute", key_func=ip_key_func)
async def resend_otp(request: Request, data: ResendOTPRequest):
    await UserServices.resend_verification_otp(data.email)
    return success_response(t(request, Msg.OTP_SENT_SUCCESSFULLY))


@router.post("/forgot-password", response_model=ApiResponse[None])
@limiter.limit("3/minute", key_func=ip_key_func)
async def forgot_password_request(request: Request, data: ForgotPasswordRequest):
    await UserServices.forgot_password_request(data)
    return success_response(t(request, Msg.PASSWORD_RESET_CODE_SENT))


@router.post("/reset-password", response_model=ApiResponse[None])
@limiter.limit("5/minute", key_func=ip_key_func)
async def reset_password(request: Request, data: ResetPasswordRequest):
    await UserServices.reset_password_with_otp(data)
    return success_response(t(request, Msg.PASSWORD_RESET_SUCCESSFULLY))
