from datetime import datetime

from beanie import PydanticObjectId
from app.models.revoked_token_model import RevokedToken
from app.services.email_otp_services import OTPService
from app.models.email_otp_model import OTPPurpose
from app.schemas.email_otp_schema import VerifyOTPRequest, ResendOTPRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.models.user_model import User
from app.schemas.user_schema import (
    LogoutRequest,
    RefreshTokenRequest,
    UserRegister,
    UserResponse,
    UserTokenData,
    UserTokenResponse,
    UserUpdatePassword,
    UserUpdateRole,
    UserUpdateProfile,
    UserAddAddress,
)
from fastapi import HTTPException, status
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pydantic import EmailStr, ValidationError
from app.core.user_role import UserRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_expiration,
    get_password_hash,
    verify_password,
)
from app.validators.address_validator import AddressValidator
from app.validators.user_validator import UserValidator


class UserServices:
    @staticmethod
    def _can_admin_manage_role(role: UserRole) -> bool:
        return role in {UserRole.SELLER, UserRole.CUSTOMER, UserRole.SUPPORT}

    @staticmethod
    async def _revoke_token(token_data: UserTokenData, expires_at: datetime) -> None:
        if not token_data.jti or not token_data.token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        existing_token = await RevokedToken.find_one(RevokedToken.jti == token_data.jti)
        if existing_token:
            return

        revoked_token = RevokedToken(
            jti=token_data.jti,
            token_type=token_data.token_type,
            user_id=token_data.user_id,
            expires_at=expires_at,
        )
        await revoked_token.insert()

    @staticmethod
    async def _decode_token_data(
        token: str,
        expected_type: str,
        invalid_detail: str,
        expired_detail: str,
    ) -> tuple[UserTokenData, datetime]:
        try:
            payload = decode_token(token)
            token_data = UserTokenData.model_validate(payload)
            if not token_data.email or token_data.token_type != expected_type or not token_data.jti:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=invalid_detail,
                )
            expires_at = get_token_expiration(payload)
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=expired_detail,
            )
        except ValidationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=invalid_detail,
            )
        except InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=invalid_detail,
            )

        return token_data, expires_at

    @staticmethod
    async def _validate_session_tokens(
        current_user: User,
        access_token: str,
        refresh_token: str,
    ) -> tuple[UserTokenData, datetime, UserTokenData, datetime]:
        access_token_data, access_expires_at = await UserServices._decode_token_data(
            access_token,
            expected_type="access",
            invalid_detail="Invalid access token",
            expired_detail="Access token has expired",
        )
        refresh_token_data, refresh_expires_at = await UserServices._decode_token_data(
            refresh_token,
            expected_type="refresh",
            invalid_detail="Invalid refresh token",
            expired_detail="Refresh token has expired",
        )

        revoked_refresh_token = await RevokedToken.find_one(RevokedToken.jti == refresh_token_data.jti)
        if revoked_refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        if access_token_data.email != current_user.email or refresh_token_data.email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tokens do not belong to the current user",
            )

        return access_token_data, access_expires_at, refresh_token_data, refresh_expires_at

    @staticmethod
    async def verify_email_registration(data: VerifyOTPRequest) -> str:
        """Logic to bridge OTP verification and User state activation."""
        
        # 1. First, let the OTPService handle the code validation logic
        await OTPService.verify_otp(data.email, data.otp_code, OTPPurpose.REGISTRATION)

        # 2. Once verified, we handle the User-specific state change
        user = await User.find_one(User.email == data.email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.is_verified:
            return "Email is already verified."

        user.is_verified = True
        await user.save()
        
        return "Email verified successfully. You can now login."

    @staticmethod
    async def resend_verification_otp(email: str) -> None:
        """Handles the logic for resending OTPs to unverified users."""
        user = await User.find_one(User.email == email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.is_verified:
            raise HTTPException(status_code=400, detail="User is already verified")

        await OTPService.create_and_send_otp(email, OTPPurpose.REGISTRATION)
        
    @staticmethod
    async def user_registration(user: UserRegister) -> UserResponse:
        UserValidator.validate_registration(user)
        user_email = await User.find_one(User.email == user.email)
        if user_email:
            if not user_email.is_verified:
                await OTPService.create_and_send_otp(user_email.email, OTPPurpose.REGISTRATION)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Email registered but not verified. A new OTP has been sent."
                )
            raise HTTPException(status_code=400, detail="Email already registered")
        
        username_exists = await User.find_one(User.user_name == user.user_name)
        if username_exists:
            raise HTTPException(status_code=400, detail="Username already taken")
        
        new_user = User(
            user_name=user.user_name,
            email=user.email,
            hashed_password=get_password_hash(user.password),
            mobile=user.mobile,
            is_verified=False,
            created_by=None,
            updated_by=None,
        )
        await new_user.insert()
        await OTPService.create_and_send_otp(new_user.email, OTPPurpose.REGISTRATION)
        return UserResponse.model_validate(new_user)

    @staticmethod
    async def get_all_users() -> list[UserResponse]:
        users = await User.find(User.is_deleted == False).to_list()
        return [UserResponse.model_validate(user) for user in users]

    @staticmethod
    async def get_my_profile(current_user: User) -> UserResponse:
        return UserResponse.model_validate(current_user)

    @staticmethod
    async def _authenticate_user(email: EmailStr, password: str) -> User:
        user = await User.find_one(User.email == email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified. Please verify your email to login."
            )
        return user

    @staticmethod
    def _build_token_response(user: User) -> UserTokenResponse:
        token_payload = {
            "sub": str(user.email),
            "user_id": str(user.id),
            "user_name": user.user_name,
            "role": user.role.value 
        }
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)
        return UserTokenResponse(access_token=access_token, refresh_token=refresh_token)

    @staticmethod
    async def login_and_issue_tokens(email: EmailStr, password: str) -> UserTokenResponse:
        authenticated_user = await UserServices._authenticate_user(email, password)
        return UserServices._build_token_response(authenticated_user)

    @staticmethod
    async def refresh_user_token(data: RefreshTokenRequest) -> UserTokenResponse:
        token_data, expires_at = await UserServices._decode_token_data(
            data.refresh_token,
            expected_type="refresh",
            invalid_detail="Invalid refresh token",
            expired_detail="Refresh token has expired",
        )

        revoked_token = await RevokedToken.find_one(RevokedToken.jti == token_data.jti)
        if revoked_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        user = await User.find_one(User.email == token_data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        await UserServices._revoke_token(token_data, expires_at)
        return UserServices._build_token_response(user)

    @staticmethod
    async def logout_user(current_user: User, access_token: str, data: LogoutRequest) -> None:
        access_token_data, access_expires_at, refresh_token_data, refresh_expires_at = (
            await UserServices._validate_session_tokens(current_user, access_token, data.refresh_token)
        )

        await UserServices._revoke_token(access_token_data, access_expires_at)
        await UserServices._revoke_token(refresh_token_data, refresh_expires_at)
        
    @staticmethod
    async def update_user_password(current_user: User, access_token: str, data: UserUpdatePassword) -> None:
        if not verify_password(data.old_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )
        if data.old_password == data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from the current password",
            )

        access_token_data, access_expires_at, refresh_token_data, refresh_expires_at = (
            await UserServices._validate_session_tokens(current_user, access_token, data.refresh_token)
        )

        current_user.hashed_password = get_password_hash(data.new_password)
        await current_user.save()
        await UserServices._revoke_token(access_token_data, access_expires_at)
        await UserServices._revoke_token(refresh_token_data, refresh_expires_at)
    
    @staticmethod
    async def reset_password_with_otp(data: ResetPasswordRequest) -> None:
        """
        Verifies the OTP and updates the user's password.
        """
        await OTPService.verify_otp(data.email, data.otp_code, OTPPurpose.PASSWORD_RESET)

        user = await User.find_one(User.email == data.email)
        if not user:
            raise HTTPException(status_code=404, detail="User account not found.")

        user.hashed_password = get_password_hash(data.new_password)
        
        await user.save()
        return
        
    @staticmethod
    async def forgot_password_request(data: ForgotPasswordRequest) -> None:
        """
        Initiates the password reset process.
        """
        user = await User.find_one(User.email == data.email)
        
        if user:
            await OTPService.create_and_send_otp(user.email, OTPPurpose.PASSWORD_RESET)
        
        return

    @staticmethod
    async def update_my_profile(current_user: User, data: UserUpdateProfile) -> UserResponse:
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return UserResponse.model_validate(current_user)

        UserValidator.validate_profile_update(data)
        
        if "user_name" in update_data:
            existing_user = await User.find_one(
                {
                    "user_name": update_data["user_name"],
                    "_id": {"$ne": current_user.id},
                    "is_deleted": {"$ne": True},
                }
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )

        for field, value in update_data.items():
            setattr(current_user, field, value)
        current_user.updated_by = current_user.id
        await current_user.save()
        return UserResponse.model_validate(current_user)

    @staticmethod
    async def update_user_profile(
        current_user: User,
        target_user_id: PydanticObjectId,
        data: UserUpdateProfile,
    ) -> UserResponse:
        target_user = await User.get(target_user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return UserResponse.model_validate(target_user)

        UserValidator.validate_profile_update(data)
        if current_user.id == target_user.id:
            return await UserServices.update_my_profile(current_user, data)

        if current_user.role == UserRole.SUPER_ADMIN:
            pass
        elif current_user.role == UserRole.ADMIN:
            if not UserServices._can_admin_manage_role(target_user.role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins can update only seller, customer, or support users",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can update only your own profile",
            )

        if "user_name" in update_data:
            existing_user = await User.find_one(
                {
                    "user_name": update_data["user_name"],
                    "_id": {"$ne": target_user.id},
                    "is_deleted": {"$ne": True},
                }
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )

        for field, value in update_data.items():
            setattr(target_user, field, value)
        target_user.updated_by = current_user.id
        await target_user.save()
        return UserResponse.model_validate(target_user)

    @staticmethod
    async def update_user_role(
        current_user: User,
        target_user_id: PydanticObjectId,
        data: UserUpdateRole,
    ) -> UserResponse:
        target_user = await User.get(target_user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if current_user.id == target_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot change your own role",
            )

        if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to update user roles",
            )

        if target_user.role == data.new_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has this role",
            )

        if current_user.role == UserRole.ADMIN:
            if target_user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot change the role of admin or super admin users",
                )

            if not UserServices._can_admin_manage_role(data.new_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins can assign only seller, customer, or support roles",
                )

        if data.new_role == UserRole.SUPER_ADMIN:
            if current_user.role != UserRole.SUPER_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the super admin can assign the super admin role",
                )

            existing_super_admin = await User.find_one(User.role == UserRole.SUPER_ADMIN)
            if existing_super_admin and existing_super_admin.id != target_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only one super admin is allowed",
                )

        if target_user.role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the super admin can manage the super admin account",
            )

        target_user.role = data.new_role
        target_user.updated_by = current_user.id
        await target_user.save()
        return UserResponse.model_validate(target_user)
    
    @staticmethod
    async def add_user_address(current_user: User, data: UserAddAddress) -> UserResponse:
        """Appends a new address to the user's address book."""
        data.address = AddressValidator.normalize_and_validate(data.address)
        # Optional: Limit the number of addresses a user can save (e.g., max 10)
        if len(current_user.addresses) >= 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum of 10 addresses allowed. Please delete an old address first."
            )
            
        current_user.addresses.append(data.address)
        current_user.updated_by = current_user.id
        await current_user.save()
        return UserResponse.model_validate(current_user)
    
    @staticmethod
    async def update_user_address(current_user: User, address_index: int, data: UserAddAddress) -> UserResponse:
        """Updates an existing address in the user's address book by its list index."""
        if address_index < 0 or address_index >= len(current_user.addresses):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found at the specified index."
            )
        data.address = AddressValidator.normalize_and_validate(data.address) 
        current_user.addresses[address_index] = data.address
        current_user.updated_by = current_user.id
        await current_user.save()
        return UserResponse.model_validate(current_user)

    @staticmethod
    async def remove_user_address(current_user: User, address_index: int) -> UserResponse:
        """Removes an address from the user's address book by its list index."""
        if address_index < 0 or address_index >= len(current_user.addresses):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found at the specified index."
            )
            
        current_user.addresses.pop(address_index)
        current_user.updated_by = current_user.id
        await current_user.save()
        return UserResponse.model_validate(current_user)

    @staticmethod
    async def delete_user(target_user_id: PydanticObjectId, current_user: User) -> bool:
        """Admins can soft-delete a user account."""
        target_user = await User.get(target_user_id)
        if not target_user or target_user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found")

        if target_user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Super Admins cannot be deleted")

        if current_user.id is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        await target_user.soft_delete(current_user.id)
        return True
