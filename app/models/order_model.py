from datetime import datetime
from enum import Enum
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field, model_validator
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.base_model import AuditDocument
from app.schemas.address_schema import Address


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class OrderPaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class OrderItemSnapshot(BaseModel):
    product_id: PydanticObjectId
    seller_id: PydanticObjectId
    sku: str
    product_name: str
    quantity: int = Field(..., gt=0)
    purchase_price: int = Field(..., ge=0, description="Snapshot of effective_price at checkout")

    @model_validator(mode="after")
    def validate_snapshot(self):
        if self.quantity <= 0:
            raise ValueError("Quantity must be greater than 0")

        if self.purchase_price < 0:
            raise ValueError("Purchase price cannot be negative")

        if not self.sku.strip():
            raise ValueError("SKU cannot be empty")

        return self


class Order(AuditDocument):
    user_id: PydanticObjectId
    seller_id: PydanticObjectId

    checkout_batch_id: str
    transaction_id: PydanticObjectId

    items: List[OrderItemSnapshot]

    shipping_address: Address
    billing_address: Address

    subtotal: int = Field(..., ge=0, description="Raw sum of seller-owned items")
    tax_amount: int = Field(..., ge=0, description="Calculated tax for this seller order")
    shipping_fee: int = Field(..., ge=0, description="Shipping charge for this seller order")
    grand_total: int = Field(..., ge=0, description="Final amount owed for this seller order")

    status: OrderStatus = Field(default=OrderStatus.PENDING)
    payment_status: OrderPaymentStatus = Field(default=OrderPaymentStatus.PENDING)
    refunded_amount: int = Field(default=0, ge=0)
    expires_at: Optional[datetime] = Field(default=None)
    cleanup_processed: bool = Field(default=False)
    
    cancellation_reason: Optional[str] = Field(default=None, max_length=500, description="Reason provided when the order was cancelled")    

    class Settings:
        name = "orders"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("seller_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("transaction_id", ASCENDING)]),
            IndexModel([("checkout_batch_id", ASCENDING)]),
            IndexModel([("checkout_batch_id", ASCENDING), ("seller_id", ASCENDING)], unique=True),
            IndexModel([("status", ASCENDING), ("expires_at", ASCENDING)]),
        ]
