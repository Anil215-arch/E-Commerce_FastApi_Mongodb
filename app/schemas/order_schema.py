from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.order_model import OrderItemSnapshot, OrderPaymentStatus, OrderStatus
from app.models.transaction_model import PaymentMethod, TransactionStatus
from app.schemas.address_schema import Address


class CheckoutRequest(BaseModel):
    shipping_address: Address = Field(..., description="Where to ship the physical products")
    billing_address: Address = Field(..., description="Address associated with the payment method")
    payment_method: PaymentMethod = Field(default=PaymentMethod.CARD, description="Chosen payment method")


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
