from datetime import datetime, timezone

from beanie import Document
from pydantic import EmailStr, Field
from pymongo import ASCENDING, IndexModel
from app.core.user_role import UserRole


    

class User(Document):
    user_name: str = Field(..., min_length=2, max_length=100, description="User name is required")
    email: EmailStr = Field(..., description="Email is required")
    hashed_password: str = Field(..., description="Unique password is required")
    mobile: str = Field(..., min_length=10, max_length=15, description="Enter your mobile no.")
    role: UserRole = Field(default=UserRole.CUSTOMER, description="User role")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("role", ASCENDING)]),
        ]
