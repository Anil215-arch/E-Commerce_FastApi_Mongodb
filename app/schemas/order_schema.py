from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.order_model import OrderItemSnapshot, OrderPaymentStatus, OrderStatus
from app.models.transaction_model import PaymentMethod, TransactionStatus
from app.schemas.address_schema import Address


class CheckoutRequest(BaseModel):
    checkout_batch_id: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Client-provided idempotency key for checkout",
    )
    shipping_address_index: int = Field(..., ge=0, description="Array index of the user's saved shipping address")
    billing_address_index: int = Field(..., ge=0, description="Array index of the user's saved billing address")
    payment_method: PaymentMethod = Field(default=PaymentMethod.CARD, description="Chosen payment method")

    @model_validator(mode="after")
    def validate_indexes(self):
        if self.shipping_address_index < 0 or self.billing_address_index < 0:
            raise ValueError("Address indexes must be non-negative")
        return self

class OrderResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    user_id: PydanticObjectId
    seller_id: PydanticObjectId
    checkout_batch_id: str
    transaction_id: PydanticObjectId
    items: List[OrderItemSnapshot]
    shipping_address: Address
    billing_address: Address
    subtotal: int
    tax_amount: int
    shipping_fee: int
    grand_total: int
    status: OrderStatus
    payment_status: OrderPaymentStatus
    refunded_amount: int
    cancellation_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class CheckoutBatchResponse(BaseModel):
    checkout_batch_id: str
    transaction_id: PydanticObjectId
    amount: int
    transaction_status: TransactionStatus
    payment_method: PaymentMethod
    orders: List[OrderResponse]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class OrderUpdateStatusRequest(BaseModel):
    status: OrderStatus = Field(..., description="The new status to apply to the order")
    
class OrderCancelRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500, description="The exact reason for cancelling the order.")
