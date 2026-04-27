from fastapi import APIRouter, Depends, status, Request
from app.core.dependencies import get_current_user, get_bearer_token
from app.models.user_model import User
from app.schemas.user_schema import UserResponse, UserUpdateProfile, UserUpdatePassword, UserAddAddress
from app.schemas.common_schema import ApiResponse
from app.services.user_services import UserServices
from app.utils.responses import success_response
from app.core.i18n import t
from app.core.message_keys import Msg
from app.core.rate_limiter import user_limiter

router = APIRouter()

@router.get("/", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_my_profile(request: Request, current_user: User = Depends(get_current_user)):
    user_profile = await UserServices.get_my_profile(current_user)
    return success_response(t(request, Msg.CURRENT_USER_FETCHED_SUCCESSFULLY), user_profile)

@user_limiter.limit("30/minute")
async def get_current_logged_in_user(request: Request, current_user: User = Depends(get_current_user)):
    user_profile = await UserServices.get_my_profile(current_user)
    return success_response(t(request, Msg.CURRENT_USER_FETCHED_SUCCESSFULLY), user_profile)

@router.patch("/", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def update_my_profile(request: Request, profile_in: UserUpdateProfile, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.update_my_profile(current_user, profile_in)
    return success_response(t(request, Msg.PROFILE_UPDATED_SUCCESSFULLY), updated_user)

@router.patch("/change-password", response_model=ApiResponse[None], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("5/minute")
async def change_password(request: Request, password_in: UserUpdatePassword, current_user: User = Depends(get_current_user), access_token: str = Depends(get_bearer_token)):
    await UserServices.update_user_password(current_user, access_token, password_in)
    return success_response(t(request, Msg.PASSWORD_CHANGED_LOGIN_AGAIN))

@router.post("/addresses", response_model=ApiResponse[UserResponse])
@user_limiter.limit("10/minute")
async def add_address(request: Request, data: UserAddAddress, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.add_user_address(current_user, data)
    return success_response(t(request, Msg.ADDRESS_ADDED_SUCCESSFULLY), updated_user)

@router.put("/addresses/{address_index}", response_model=ApiResponse[UserResponse])
@user_limiter.limit("10/minute")
async def update_address(
    request: Request,
    address_index: int,
    data: UserAddAddress,
    current_user: User = Depends(get_current_user)
):
    updated_user = await UserServices.update_user_address(current_user, address_index, data)
    return success_response(t(request, Msg.ADDRESS_UPDATED_SUCCESSFULLY), updated_user)

@router.delete("/addresses/{address_index}", response_model=ApiResponse[UserResponse])
@user_limiter.limit("10/minute")
async def remove_address(request: Request, address_index: int, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.remove_user_address(current_user, address_index)
    return success_response(t(request, Msg.ADDRESS_REMOVED_SUCCESSFULLY), updated_user)
