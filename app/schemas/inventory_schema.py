from beanie import PydanticObjectId
from pydantic import BaseModel, Field, model_validator


class InventoryAdjustRequest(BaseModel):
    request_id: str = Field(..., min_length=8, max_length=120, description="Idempotency key for inventory adjustment")
    delta: int = Field(..., description="Relative stock change. Positive adds stock, negative removes stock")
    reason: str = Field(..., min_length=5, max_length=200, description="Audit reason for this stock adjustment")

    @model_validator(mode="after")
    def validate_quantity(self):
        if self.delta == 0:
            raise ValueError("delta must not be 0")
        if abs(self.delta) > 100000:
            raise ValueError("abs(delta) must be <= 100000")
        return self


class InventoryVariantResponse(BaseModel):
    product_id: PydanticObjectId
    sku: str
    available_stock: int = Field(..., ge=0)
    reserved_stock: int = Field(..., ge=0)
    total_stock: int = Field(..., ge=0)
