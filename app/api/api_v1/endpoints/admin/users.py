from fastapi import APIRouter, Depends, status, Request
from beanie import PydanticObjectId
from typing import List
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.user_schema import UserResponse, UserUpdateRole, UserUpdateProfile
from app.schemas.common_schema import ApiResponse
from app.services.user_services import UserServices
from app.utils.responses import success_response

router = APIRouter()

@router.get("/", response_model=ApiResponse[List[UserResponse]], response_model_by_alias=False)
@user_limiter.limit("30/minute")
async def get_all_users(request: Request, current_user: User = Depends(get_current_user)):
    users = await UserServices.get_all_users()
    return success_response("Users fetched successfully", users)

@router.patch("/{id}/role", response_model=ApiResponse[UserResponse], response_model_by_alias=False)
@user_limiter.limit("10/minute")
async def update_user_role(request: Request, id: PydanticObjectId, role_in: UserUpdateRole, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.update_user_role(current_user, id, role_in)
    return success_response("User role updated successfully", updated_user)

@router.patch("/{id}", response_model=ApiResponse[UserResponse], response_model_by_alias=False)
@user_limiter.limit("10/minute")
async def update_user_profile(request: Request, id: PydanticObjectId, profile_in: UserUpdateProfile, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.update_user_profile(current_user, id, profile_in)
    return success_response("User profile updated successfully", updated_user)

@router.delete("/{id}", response_model=ApiResponse[bool])
@user_limiter.limit("10/minute")
async def delete_user(request: Request, id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    success = await UserServices.delete_user(id, current_user)
    return success_response("User deleted successfully", success)