import re
from beanie import PydanticObjectId
from pydantic import BaseModel, Field, model_validator


class InventoryAdjustRequest(BaseModel):
    request_id: str = Field(..., min_length=8, max_length=120, description="Idempotency key for inventory adjustment")
    delta: int = Field(..., description="Relative stock change. Positive adds stock, negative removes stock")
    reason: str = Field(..., min_length=5, max_length=200, description="Audit reason for this stock adjustment")

    @model_validator(mode="after")
    def validate_fields(self):
        if self.delta == 0:
            raise ValueError("delta must not be 0")

        if abs(self.delta) > 100000:
            raise ValueError("abs(delta) must be <= 100000")

        if not re.match(r"^[a-zA-Z0-9_-]+$", self.request_id):
            raise ValueError("request_id contains invalid characters")
        if not self.request_id.strip():
            raise ValueError("request_id cannot be empty or whitespace")
        if self.reason.strip() != self.reason:
            raise ValueError("reason must not have leading/trailing spaces")

        if len(self.reason.split()) < 2:
            raise ValueError("reason must be more descriptive")

        return self


class InventoryVariantResponse(BaseModel):
    product_id: PydanticObjectId
    sku: str
    available_stock: int = Field(..., ge=0)
    reserved_stock: int = Field(..., ge=0)
    total_stock: int = Field(..., ge=0)
    
    @model_validator(mode="after")
    def validate_stock_consistency(self):
        if self.available_stock < 0 or self.reserved_stock < 0:
            raise ValueError("Stock values cannot be negative")

        if self.total_stock != self.available_stock + self.reserved_stock:
            raise ValueError("total_stock mismatch")

        return self
