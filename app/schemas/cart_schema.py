from pydantic import BaseModel, Field, field_serializer
from beanie import PydanticObjectId
from typing import List, Optional
from app.schemas.product_variant_schema import ProductVariantResponse

class CartItemAdd(BaseModel):
    product_id: PydanticObjectId
    sku: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9\-_]+$")
    quantity: int = Field(default=1, ge=1, le=10)

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, le=10, description="New exact quantity")

class CartItemDetailed(BaseModel):
    product_id: PydanticObjectId
    name: str
    brand: str
    sku: str
    image: Optional[str] = None
    variant: Optional[ProductVariantResponse] = None
    requested_quantity: int
    effective_quantity: int
    subtotal: int
    is_available: bool
    available_stock: int

    @field_serializer("product_id", "sku")
    def serialize_id(self, value):
        return str(value) if value else None

class CartResponse(BaseModel):
    items: List[CartItemDetailed]
    total_quantity: int
    total_price: int