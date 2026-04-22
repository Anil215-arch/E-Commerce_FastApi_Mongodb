from beanie import PydanticObjectId
from pymongo import ASCENDING, IndexModel
from app.models.base_model import AuditDocument
from pydantic import Field, model_validator

class Wishlist(AuditDocument):
    user_id: PydanticObjectId
    product_id: PydanticObjectId
    sku: str = Field(..., min_length=3, max_length=100)

    @model_validator(mode="after")
    def validate_wishlist_item(self):
        if not self.sku.strip():
            raise ValueError("SKU cannot be empty or whitespace")
        return self
    
    class Settings:
        name = "wishlists"
        indexes = [
            IndexModel([("user_id", ASCENDING)]),
            IndexModel(
                [("user_id", ASCENDING), ("product_id", ASCENDING), ("sku", ASCENDING)],
                unique=True,
                name="unique_user_wishlist_item"
            )
        ]