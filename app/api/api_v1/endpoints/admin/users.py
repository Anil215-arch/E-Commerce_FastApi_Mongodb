from fastapi import APIRouter, Depends, status
from beanie import PydanticObjectId
from typing import List

from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.user_schema import UserResponse, UserUpdateRole, UserUpdateProfile
from app.schemas.common_schema import ApiResponse
from app.services.user_services import UserServices
from app.utils.responses import success_response

router = APIRouter()

@router.get("/", response_model=ApiResponse[List[UserResponse]], response_model_by_alias=False)
async def get_all_users(current_user: User = Depends(get_current_user)):
    users = await UserServices.get_all_users()
    return success_response("Users fetched successfully", users)

@router.patch("/{id}/role", response_model=ApiResponse[UserResponse], response_model_by_alias=False)
async def update_user_role(id: PydanticObjectId, role_in: UserUpdateRole, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.update_user_role(current_user, id, role_in)
    return success_response("User role updated successfully", updated_user)

@router.patch("/{id}", response_model=ApiResponse[UserResponse], response_model_by_alias=False)
async def update_user_profile(id: PydanticObjectId, profile_in: UserUpdateProfile, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.update_user_profile(current_user, id, profile_in)
    return success_response("User profile updated successfully", updated_user)

@router.delete("/{id}", response_model=ApiResponse[bool])
async def delete_user(id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    success = await UserServices.delete_user(id, current_user)
    return success_response("User deleted successfully", success)