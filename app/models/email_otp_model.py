from datetime import datetime, timezone
from enum import Enum
from beanie import Document
from pydantic import Field, field_validator
from pymongo import IndexModel, ASCENDING

class OTPPurpose(str, Enum):
    """
    Strict enumeration to prevent 'Forgot Password' OTPs 
    from being used for 'Registration' validation.
    """
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"

class EmailOTPVerification(Document):
    email: str = Field(..., description="The email address tied to this OTP")
    hashed_otp: str = Field(..., description="The 6-digit code (Store hashed in production)")
    purpose: OTPPurpose = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(..., description="The exact time this OTP becomes invalid")
    
    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    class Settings:
        name = "email_otp_verifications"
        indexes = [
            IndexModel([("email", ASCENDING)]),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0)
        ]