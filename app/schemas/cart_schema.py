from pydantic import BaseModel, Field, field_serializer
from beanie import PydanticObjectId
from typing import List, Optional
from app.schemas.product_variant_schema import ProductVariantResponse

class CartItemAdd(BaseModel):
    product_id: PydanticObjectId
    sku: str
    quantity: int = Field(default=1, ge=1)

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, description="New exact quantity")

class CartItemDetailed(BaseModel):
    product_id: PydanticObjectId
    name: str
    brand: str
    sku: str
    image: Optional[str] = None
    variant: ProductVariantResponse
    quantity: int
    subtotal: int

    @field_serializer("product_id")
    def serialize_id(self, value):
        return str(value)

class CartResponse(BaseModel):
    items: List[CartItemDetailed]
    total_quantity: int
    total_price: int