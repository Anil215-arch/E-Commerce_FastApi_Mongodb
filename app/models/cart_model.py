from datetime import datetime
from typing import List
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import IndexModel, ASCENDING

class CartItem(BaseModel):
    """
    Embedded document representing a single item in the cart.
    Kept as a pure reference to the Product catalog.
    """
    product_id: PydanticObjectId
    sku: str
    quantity: int = Field(default=1, ge=1)

class Cart(Document):
    """
    The main Cart document. A strict 1-to-1 relationship with a User.
    """
    user_id: PydanticObjectId
    items: List[CartItem] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "carts"
        indexes = [
            IndexModel([("user_id", ASCENDING)], unique=True) 
        ]