from datetime import datetime
from app.schemas.address_schema import Address
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator
from beanie import PydanticObjectId
from app.core.user_role import UserRole


class UserRegister(BaseModel):
    user_name: str = Field(..., min_length=2, max_length=100, description="User name is required")
    email: EmailStr = Field(..., description="Email is required")
    password: str = Field(..., min_length=8, description="Password is required")
    mobile: str = Field(..., min_length=10, max_length=15, description="Enter your mobile no.")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_name": "RockStar",
                "email": "rockstar@gmail.com",
                "password": "Rock142@#%Star562",
                "mobile": "9876543210",
            }
        }
    )


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="Email is required")
    password: str = Field(..., min_length=8, description="Password is required")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "rockstar@gmail.com",
                "password": "Rock142@#%Star562"
            }
        }
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token is required")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token is required to log out the current session")


class UserResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    user_name: str
    email: EmailStr
    mobile: str
    role: UserRole
    is_verified: bool
    addresses: list[Address] = []
    created_at: datetime
    
    @field_serializer("id")
    def serialize_object_id(self, value):
        return str(value) if value else None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserTokenData(BaseModel):
    email: EmailStr | None = Field(default=None, alias="sub")
    user_id: str | None = None
    user_name: str | None = None
    role: UserRole | None = None
    token_type: str | None = None
    jti: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value
    model_config = ConfigDict(populate_by_name=True)
    

class UserUpdatePassword(BaseModel):
    old_password: str = Field(..., min_length=8, description="Old password is required")
    new_password: str = Field(..., min_length=8, description="New password is required")
    refresh_token: str = Field(..., description="Current session refresh token is required")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "old_password": "OldPass123!",
                "new_password": "NewPass456@",
                "refresh_token": "your_current_refresh_token"
            }
        }
    )
    
class UserUpdateRole(BaseModel):
    new_role: UserRole = Field(..., description="New role is required")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_role": "admin"
            }
        }
    )


class UserUpdateProfile(BaseModel):
    user_name: str | None = Field(default=None, min_length=2, max_length=100, description="Updated user name")
    mobile: str | None = Field(default=None, min_length=10, max_length=15, description="Updated mobile number")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_name": "RockStar Updated",
                "mobile": "9876501234"
            }
        }
    )
    
    
class UserAddAddress(BaseModel):
    address: Address = Field(..., description="The new address to add to the address book")