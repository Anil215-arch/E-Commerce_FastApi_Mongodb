from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

class VerifyOTPRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address to verify")
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value
    
    @model_validator(mode="after")
    def validate_otp_code_digits(self):
        if not self.otp_code.isdigit():
            raise ValueError("OTP code must contain exactly 6 digits")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "rockstar@gmail.com",
                "otp_code": "123456"
            }
        }
    )

class ResendOTPRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address to resend OTP to")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "rockstar@gmail.com"
            }
        }
    )
    
class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address to receive the password reset OTP")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "rockstar@gmail.com"
            }
        }
    )

class ResetPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address associated with the account")
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
    new_password: str = Field(..., min_length=8, description="The new password for the account")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def validate_fields(self):
        if not self.otp_code.isdigit():
            raise ValueError("OTP code must contain exactly 6 digits")
        if not self.new_password.strip():
            raise ValueError("New password cannot be empty or whitespace")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "rockstar@gmail.com",
                "otp_code": "123456",
                "new_password": "NewStrongPassword123!"
            }
        }
    )