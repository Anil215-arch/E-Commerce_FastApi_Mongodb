from fastapi import APIRouter, Depends, status
from beanie import PydanticObjectId
from app.models.user_model import User
from app.core.dependencies import RoleChecker, get_bearer_token, get_current_user
from app.core.user_role import UserRole
from app.schemas.user_schema import (
    LogoutRequest,
    RefreshTokenRequest,
    UserLogin,
    UserRegister,
    UserResponse,
    UserTokenResponse,
    UserUpdatePassword,
    UserUpdateProfile,
    UserUpdateRole,
    UserAddAddress,
)
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.services.user_services import UserServices


router = APIRouter()
view_user_access = Depends(RoleChecker([UserRole.SUPER_ADMIN, UserRole.ADMIN]))


@router.get("/", response_model=ApiResponse[list[UserResponse]], response_model_by_alias=False)
async def get_all_users(
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = view_user_access,
):
    users = await UserServices.get_all_users()
    return success_response("Users fetched successfully", users)

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


@router.get("/me", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_current_logged_in_user(current_user: User = Depends(get_current_user)):
    user_profile = await UserServices.get_my_profile(current_user)
    return success_response("Current user fetched successfully", user_profile)


@router.patch("/me", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def update_my_profile(
    profile_in: UserUpdateProfile,
    current_user: User = Depends(get_current_user),
):
    updated_user = await UserServices.update_my_profile(current_user, profile_in)
    return success_response("Profile updated successfully", updated_user)


@router.patch("/change-password", response_model=ApiResponse[None], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def change_old_password(
    password_in: UserUpdatePassword,
    _current_user: User = Depends(get_current_user),
    access_token: str = Depends(get_bearer_token),
):
    await UserServices.update_user_password(_current_user, access_token, password_in)
    return success_response("Password changed successfully. Please log in again.")


@router.patch("/{id}/role", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def update_user_role(
    id: PydanticObjectId,
    role_in: UserUpdateRole,
    current_user: User = Depends(get_current_user),
):
    updated_user = await UserServices.update_user_role(current_user, id, role_in)
    return success_response("User role updated successfully", updated_user)


@router.patch("/{id}", response_model=ApiResponse[UserResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def update_user_profile(
    id: PydanticObjectId,
    profile_in: UserUpdateProfile,
    current_user: User = Depends(get_current_user),
):
    updated_user = await UserServices.update_user_profile(current_user, id, profile_in)
    return success_response("User profile updated successfully", updated_user)

@router.post("/me/addresses", response_model=ApiResponse[UserResponse])
async def add_address(
    data: UserAddAddress,
    current_user: User = Depends(get_current_user)
):
    """
    Appends a new shipping/billing address to the user's profile.
    """
    updated_user = await UserServices.add_user_address(current_user, data)
    return success_response("Address added successfully", updated_user)


@router.delete("/me/addresses/{address_index}", response_model=ApiResponse[UserResponse])
async def remove_address(
    address_index: int,
    current_user: User = Depends(get_current_user)
):
    """
    Deletes an address from the user's profile based on its array index (0-based).
    """
    updated_user = await UserServices.remove_user_address(current_user, address_index)
    return success_response("Address removed successfully", updated_user)


@router.delete("/{id}", response_model=ApiResponse[bool], status_code=status.HTTP_200_OK)
async def delete_user(
    id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
    _authorized_user: User = view_user_access, # Reusing Admin check
):
    """
    Admin only: Soft-deletes a user account.
    """
    success = await UserServices.delete_user(id, current_user)
    return success_response("User deleted successfully", success)