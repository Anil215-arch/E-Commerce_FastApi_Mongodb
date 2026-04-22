from pydantic import Field, model_validator
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

    @model_validator(mode="after")
    def validate_stock_math(self):
        expected_new = self.previous_stock + self.delta
        if self.new_stock != expected_new:
            raise ValueError(
                f"Stock mismatch: expected {expected_new}, got {self.new_stock}"
            )

        if self.previous_stock < 0:
            raise ValueError("previous_stock cannot be negative")

        if self.delta == 0:
            raise ValueError("delta cannot be zero")

        if not self.sku.strip():
            raise ValueError("sku cannot be empty or whitespace")

        if not self.request_id.strip():
            raise ValueError("request_id cannot be empty or whitespace")

        if not self.reason.strip():
            raise ValueError("reason cannot be empty or whitespace")
        
        return self
    
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
