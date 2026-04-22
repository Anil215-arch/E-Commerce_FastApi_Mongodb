from pydantic import BaseModel, Field

class Address(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Recipient's full name")
    phone_number: str = Field(..., min_length=10, max_length=20, description="Contact phone number")
    street_address: str = Field(..., min_length=5, max_length=255, description="House number, building, street")
    city: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=4, max_length=20)
    state: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)