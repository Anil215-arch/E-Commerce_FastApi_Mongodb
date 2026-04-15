from datetime import datetime
from typing import List
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import IndexModel, ASCENDING

class CartItem(BaseModel):
    product_id: PydanticObjectId
    sku: str  
    quantity: int = Field(default=1, ge=1)

class Cart(Document):
    user_id: PydanticObjectId
    items: List[CartItem] = Field(default_factory=list)
    version: int = 1  
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "carts"
        indexes = [
            IndexModel([("user_id", ASCENDING)], unique=True) 
        ]