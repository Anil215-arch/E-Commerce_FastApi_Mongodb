from fastapi import APIRouter, Depends, status
from app.core.dependencies import get_current_user, get_bearer_token
from app.models.user_model import User
from app.schemas.user_schema import UserResponse, UserUpdateProfile, UserUpdatePassword, UserAddAddress
from app.schemas.common_schema import ApiResponse
from app.services.user_services import UserServices
from app.utils.responses import success_response

router = APIRouter()

@router.get("/", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    user_profile = await UserServices.get_my_profile(current_user)
    return success_response("Current user fetched successfully", user_profile)

@router.patch("/", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def update_my_profile(profile_in: UserUpdateProfile, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.update_my_profile(current_user, profile_in)
    return success_response("Profile updated successfully", updated_user)

@router.patch("/change-password", response_model=ApiResponse[None], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def change_password(password_in: UserUpdatePassword, current_user: User = Depends(get_current_user), access_token: str = Depends(get_bearer_token)):
    await UserServices.update_user_password(current_user, access_token, password_in)
    return success_response("Password changed successfully. Please log in again.")

@router.post("/addresses", response_model=ApiResponse[UserResponse])
async def add_address(data: UserAddAddress, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.add_user_address(current_user, data)
    return success_response("Address added successfully", updated_user)

@router.put("/addresses/{address_index}", response_model=ApiResponse[UserResponse])
async def update_address(
    address_index: int,
    data: UserAddAddress,
    current_user: User = Depends(get_current_user)
):
    updated_user = await UserServices.update_user_address(current_user, address_index, data)
    return success_response("Address updated successfully", updated_user)

@router.delete("/addresses/{address_index}", response_model=ApiResponse[UserResponse])
async def remove_address(address_index: int, current_user: User = Depends(get_current_user)):
    updated_user = await UserServices.remove_user_address(current_user, address_index)
    return success_response("Address removed successfully", updated_user)