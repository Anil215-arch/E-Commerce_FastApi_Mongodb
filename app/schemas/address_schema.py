from pydantic import BaseModel, Field, field_validator

from app.core.i18n import SUPPORTED_LANGUAGES

class Address(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Recipient's full name")
    phone_number: str = Field(..., min_length=10, max_length=15, pattern=r"^\+?[1-9]\d{9,14}$", description="Contact phone number")
    street_address: str = Field(..., min_length=5, max_length=255, description="House number, building, street")

    city: str = Field(..., min_length=2, max_length=100, description="City")
    postal_code: str = Field(..., min_length=4, max_length=20, description="Postal code")
    state: str = Field(..., min_length=2, max_length=100, description="State")
    country: str = Field(..., min_length=2, max_length=100, description="Country")
    
    language: str = Field(
        default="en",
        description="Language/script used for this address text",
    )

    @field_validator("*", mode="before")
    @classmethod
    def strip_all(cls, value):
        return value.strip() if isinstance(value, str) else value
    
    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if value not in SUPPORTED_LANGUAGES:
            raise ValueError("Invalid address language.")
        return value