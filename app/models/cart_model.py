from datetime import datetime, timezone
from typing import List
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, model_validator
from pymongo import IndexModel, ASCENDING

class CartItem(BaseModel):
    product_id: PydanticObjectId
    sku: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9\-_]+$")
    quantity: int = Field(default=1, ge=1, le=10)

class Cart(Document):
    user_id: PydanticObjectId
    items: List[CartItem] = Field(default_factory=list, max_length=20)
    version: int = Field(default=1, ge=1) 
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @model_validator(mode="after")
    def validate_unique_items(self):
        seen = set()
        for item in self.items:
            key = (str(item.product_id), item.sku)
            if key in seen:
                raise ValueError("Duplicate cart items are not allowed")
            seen.add(key)
        return self

    class Settings:
        name = "carts"
        indexes = [
            IndexModel([("user_id", ASCENDING)], unique=True) 
        ]