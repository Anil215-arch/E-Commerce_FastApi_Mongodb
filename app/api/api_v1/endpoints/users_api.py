from fastapi import APIRouter, Depends, Request, status
from beanie import PydanticObjectId
from typing import List
from app.core.dependencies import get_current_user, get_bearer_token, RoleChecker
from app.core.i18n import t
from app.core.language_resolver import resolve_user_language
from app.core.message_keys import Msg
from app.core.user_role import UserRole
from app.models.user_model import User
from app.schemas.user_schema import (
    UserResponse, UserUpdateProfile, UserUpdatePassword, UserAddAddress,
    UserUpdateRole
)
from app.schemas.common_schema import ApiResponse
from app.services.user_services import UserServices
from app.utils.responses import success_response
from app.core.rate_limiter import user_limiter

router = APIRouter()
admin_dependency = Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))


@router.get("/me", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_current_logged_in_user(request: Request, current_user: User = Depends(get_current_user)):
    language = resolve_user_language(current_user, request)
    user_profile = await UserServices.get_my_profile(current_user)
    return success_response(t(request, Msg.CURRENT_USER_FETCHED_SUCCESSFULLY, language=language), user_profile)


@router.patch("/me", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def update_my_profile(request: Request, profile_in: UserUpdateProfile, current_user: User = Depends(get_current_user)):
    language = resolve_user_language(current_user, request)
    updated_user = await UserServices.update_my_profile(current_user, profile_in)
    return success_response(t(request, Msg.PROFILE_UPDATED_SUCCESSFULLY, language=language), updated_user)


@router.patch("/me/change-password", response_model=ApiResponse[None], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("5/minute")
async def change_password(request: Request, password_in: UserUpdatePassword, current_user: User = Depends(get_current_user), access_token: str = Depends(get_bearer_token)):
    language = resolve_user_language(current_user, request)
    await UserServices.update_user_password(current_user, access_token, password_in)
    return success_response(t(request, Msg.PASSWORD_CHANGED_LOGIN_AGAIN, language=language))


@router.post("/me/addresses", response_model=ApiResponse[UserResponse])
@user_limiter.limit("10/minute")
async def add_address(request: Request, data: UserAddAddress, current_user: User = Depends(get_current_user)):
    language = resolve_user_language(current_user, request)
    updated_user = await UserServices.add_user_address(current_user, data)
    return success_response(t(request, Msg.ADDRESS_ADDED_SUCCESSFULLY, language=language), updated_user)


@router.put("/me/addresses/{address_index}", response_model=ApiResponse[UserResponse])
@user_limiter.limit("10/minute")
async def update_address(
    request: Request,
    address_index: int,
    data: UserAddAddress,
    current_user: User = Depends(get_current_user)
):
    language = resolve_user_language(current_user, request)
    updated_user = await UserServices.update_user_address(current_user, address_index, data)
    return success_response(t(request, Msg.ADDRESS_UPDATED_SUCCESSFULLY, language=language), updated_user)


@router.delete("/me/addresses/{address_index}", response_model=ApiResponse[UserResponse])
@user_limiter.limit("10/minute")
async def remove_address(request: Request, address_index: int, current_user: User = Depends(get_current_user)):
    language = resolve_user_language(current_user, request)
    updated_user = await UserServices.remove_user_address(current_user, address_index)
    return success_response(t(request, Msg.ADDRESS_REMOVED_SUCCESSFULLY, language=language), updated_user)


@router.get("", response_model=ApiResponse[List[UserResponse]], response_model_by_alias=False, dependencies=[admin_dependency])
@user_limiter.limit("30/minute")
async def list_all_users(request: Request, current_user: User = Depends(get_current_user)):
    users = await UserServices.get_all_users()
    language = resolve_user_language(current_user, request)
    return success_response(t(request, Msg.USERS_FETCHED_SUCCESSFULLY, language=language), users)


@router.patch("/{id}/role", response_model=ApiResponse[UserResponse], response_model_by_alias=False, dependencies=[admin_dependency])
@user_limiter.limit("10/minute")
async def update_user_role(request: Request, id: PydanticObjectId, role_in: UserUpdateRole, current_user: User = Depends(get_current_user)):
    language = resolve_user_language(current_user, request)
    updated_user = await UserServices.update_user_role(current_user, id, role_in)
    return success_response(t(request, Msg.USER_ROLE_UPDATED_SUCCESSFULLY, language=language), updated_user)


@router.patch("/{id}", response_model=ApiResponse[UserResponse], response_model_by_alias=False, dependencies=[admin_dependency])
@user_limiter.limit("10/minute")
async def update_user_profile(request: Request, id: PydanticObjectId, profile_in: UserUpdateProfile, current_user: User = Depends(get_current_user)):
    language = resolve_user_language(current_user, request)
    updated_user = await UserServices.update_user_profile(current_user, id, profile_in)
    return success_response(t(request, Msg.USER_PROFILE_UPDATED_SUCCESSFULLY, language=language), updated_user)


@router.delete("/{id}", response_model=ApiResponse[bool], dependencies=[admin_dependency])
@user_limiter.limit("10/minute")
async def delete_user(request: Request, id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    language = resolve_user_language(current_user, request)
    success = await UserServices.delete_user(id, current_user)
    return success_response(t(request, Msg.USER_DELETED_SUCCESSFULLY, language=language), success)
