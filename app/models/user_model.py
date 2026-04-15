from datetime import datetime, timezone
from typing import List
from app.schemas.address_schema import Address
from beanie import Document
from pydantic import EmailStr, Field, field_validator
from pymongo import ASCENDING, IndexModel
from app.core.user_role import UserRole
from app.models.base_model import AuditDocument

    

class User(AuditDocument):
    user_name: str = Field(..., min_length=2, max_length=100, description="User name is required")
    email: EmailStr = Field(..., description="Email is required")
    hashed_password: str = Field(..., description="Unique password is required")
    mobile: str = Field(..., min_length=10, max_length=15, description="Enter your mobile no.")
    role: UserRole = Field(default=UserRole.CUSTOMER, description="User role")
    is_verified: bool = Field(default=False, description="False until email OTP is verified")
    addresses: List[Address] = Field(default_factory=list, description="User's saved addresses")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value
    
    class Settings:
        name = "users"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("user_name", ASCENDING)], unique=True),
            IndexModel([("role", ASCENDING)]),
            IndexModel(
                [("created_at", ASCENDING)], 
                expireAfterSeconds=86400,
                partialFilterExpression={"is_verified": False},
                name="unverified_user_ttl"
            )
        ]
