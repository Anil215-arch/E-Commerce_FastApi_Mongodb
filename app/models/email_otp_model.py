from datetime import datetime, timezone
from enum import Enum
from beanie import Document
from pydantic import Field, field_validator, model_validator
from pymongo import IndexModel, ASCENDING

class OTPPurpose(str, Enum):
    """
    Strict enumeration to prevent 'Forgot Password' OTPs 
    from being used for 'Registration' validation.
    """
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"

class EmailOTPVerification(Document):
    email: str = Field(..., min_length=5, max_length=254, description="The email address tied to this OTP")
    hashed_otp: str = Field(..., min_length=20, max_length=500, description="The hashed OTP value")
    purpose: OTPPurpose = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(..., description="The exact time this OTP becomes invalid")
    attempts: int = Field(default=0, ge=0, description="Tracks failed verification attempts to prevent brute-forcing")
    
    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def validate_otp_record(self):
        if not self.email.strip():
            raise ValueError("Email cannot be empty or whitespace")

        if not self.hashed_otp.strip():
            raise ValueError("Hashed OTP cannot be empty or whitespace")

        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")

        return self

    class Settings:
        name = "email_otp_verifications"
        indexes = [
            IndexModel([("email", ASCENDING)]),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0)
        ]