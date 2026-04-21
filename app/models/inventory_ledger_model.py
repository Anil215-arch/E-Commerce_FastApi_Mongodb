from pydantic import Field
from pymongo import DESCENDING, IndexModel
from beanie import PydanticObjectId

from app.models.base_model import AuditDocument


class InventoryLedger(AuditDocument):
    product_id: PydanticObjectId
    sku: str = Field(..., min_length=1, max_length=120)
    user_id: PydanticObjectId  # legacy alias for actor_user_id
    actor_user_id: PydanticObjectId
    owner_seller_id: PydanticObjectId
    request_id: str = Field(..., min_length=8, max_length=120)
    delta: int
    previous_stock: int = Field(..., ge=0)
    new_stock: int = Field(..., ge=0)
    reason: str = Field(..., min_length=5, max_length=200)

    class Settings:
        name = "inventory_ledger"
        indexes = [
            IndexModel([("product_id", DESCENDING), ("sku", DESCENDING), ("created_at", DESCENDING)]),
            IndexModel([("user_id", DESCENDING), ("created_at", DESCENDING)]),
            IndexModel([("actor_user_id", DESCENDING), ("created_at", DESCENDING)]),
            IndexModel([("owner_seller_id", DESCENDING), ("created_at", DESCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("product_id", DESCENDING), ("sku", DESCENDING), ("request_id", DESCENDING)], unique=True),
        ]
