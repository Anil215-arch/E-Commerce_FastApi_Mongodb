from beanie import PydanticObjectId
from pymongo import ASCENDING, IndexModel
from app.models.base_model import AuditDocument

class Wishlist(AuditDocument):
    user_id: PydanticObjectId
    product_id: PydanticObjectId
    sku: str

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