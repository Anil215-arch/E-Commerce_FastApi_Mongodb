from beanie import PydanticObjectId
from pydantic import BaseModel, Field, ConfigDict, field_serializer, model_validator

class WishlistAddRequest(BaseModel):
    product_id: PydanticObjectId = Field(..., description="The ID of the product")
    sku: str = Field(..., min_length=3, max_length=100, description="The specific variant SKU")
    
    @model_validator(mode="before")
    @classmethod
    def normalize_sku(cls, data):
        if isinstance(data, dict) and "sku" in data and isinstance(data["sku"], str):
            data["sku"] = data["sku"].strip()
        return data

class WishlistPopulatedResponse(BaseModel):
    wishlist_id: PydanticObjectId = Field(alias="_id")
    product_id: PydanticObjectId
    name: str
    brand: str
    sku: str
    price: int
    image: str | None

    @field_serializer("wishlist_id", "product_id")
    def serialize_id(self, value):
        return str(value)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)