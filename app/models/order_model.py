from datetime import datetime, timezone
from enum import Enum
from typing import List
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from app.schemas.address_schema import Address
from app.models.base_model import AuditDocument

class OrderStatus(str, Enum):
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"

class OrderItemSnapshot(BaseModel):
    product_id: PydanticObjectId
    sku: str
    quantity: int
    purchase_price: int = Field(..., description="Snapshot of effective_price at checkout")

class Order(AuditDocument):
    user_id: PydanticObjectId
    items: List[OrderItemSnapshot]
    
    # Logistics Snapshots
    shipping_address: Address
    billing_address: Address
    
    # Financial Engine
    subtotal: int = Field(..., ge=0, description="Raw sum of items")
    tax_amount: int = Field(..., ge=0, description="Calculated tax")
    shipping_fee: int = Field(..., ge=0, description="Cost of delivery")
    grand_total: int = Field(..., ge=0, description="Final amount owed")
    
    status: OrderStatus = Field(default=OrderStatus.PENDING)

    class Settings:
        name = "orders"