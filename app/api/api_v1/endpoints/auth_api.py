from fastapi import APIRouter, Depends, Request, status
from app.core.dependencies import get_current_user, get_bearer_token, resolve_request_language
from app.core.language_resolver import resolve_user_language
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
async def register_user(
    request: Request,
    user_in: UserRegister,
    language: str = Depends(resolve_request_language),
):
    created_user = await UserServices.user_registration(user_in)
    return success_response(t(request, Msg.USER_REGISTERED_SUCCESSFULLY, language=language), created_user)


@router.post("/login", response_model=ApiResponse[UserTokenResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute", key_func=ip_key_func)
async def login_user(
    request: Request,
    user_in: UserLogin,
    language: str = Depends(resolve_request_language),
):
    token_response = await UserServices.login_and_issue_tokens(user_in.email, user_in.password)
    return success_response(t(request, Msg.USER_LOGGED_IN_SUCCESSFULLY, language=language), token_response)


@router.post("/refresh", response_model=ApiResponse[UserTokenResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def refresh_token(
    request: Request,
    token_in: RefreshTokenRequest,
    language: str = Depends(resolve_request_language),
):
    token_response = await UserServices.refresh_user_token(token_in)
    return success_response(t(request, Msg.TOKEN_REFRESHED_SUCCESSFULLY, language=language), token_response)


@router.post("/logout", response_model=ApiResponse[None], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def logout_user(
    request: Request,
    logout_in: LogoutRequest,
    current_user: User = Depends(get_current_user),
    access_token: str = Depends(get_bearer_token),
):
    await UserServices.logout_user(current_user, access_token, logout_in)
    language = resolve_user_language(current_user, request)
    return success_response(t(request, Msg.USER_LOGGED_OUT_SUCCESSFULLY, language=language))


@router.post("/verify-registration")
@limiter.limit("10/minute", key_func=ip_key_func)
async def verify_registration(
    request: Request,
    data: VerifyOTPRequest,
    language: str = Depends(resolve_request_language),
):
    message = await UserServices.verify_email_registration(data)
    return success_response(t(request, message, language=language))


@router.post("/resend-otp")
@limiter.limit("3/minute", key_func=ip_key_func)
async def resend_otp(
    request: Request,
    data: ResendOTPRequest,
    language: str = Depends(resolve_request_language),
):
    await UserServices.resend_verification_otp(data.email)
    return success_response(t(request, Msg.OTP_SENT_SUCCESSFULLY, language=language))


@router.post("/forgot-password", response_model=ApiResponse[None])
@limiter.limit("3/minute", key_func=ip_key_func)
async def forgot_password_request(
    request: Request,
    data: ForgotPasswordRequest,
    language: str = Depends(resolve_request_language),
):
    await UserServices.forgot_password_request(data)
    return success_response(t(request, Msg.PASSWORD_RESET_CODE_SENT, language=language))


@router.post("/reset-password", response_model=ApiResponse[None])
@limiter.limit("5/minute", key_func=ip_key_func)
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    language: str = Depends(resolve_request_language),
):
    await UserServices.reset_password_with_otp(data)
    return success_response(t(request, Msg.PASSWORD_RESET_SUCCESSFULLY, language=language))
