from datetime import datetime
from typing import List
from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field
from app.models.order_model import OrderStatus, OrderItemSnapshot
from app.schemas.address_schema import Address

class CheckoutRequest(BaseModel):
    shipping_address: Address = Field(..., description="Where to ship the physical products")
    billing_address: Address = Field(..., description="Address associated with the payment method")

class OrderResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    user_id: PydanticObjectId
    items: List[OrderItemSnapshot]
    shipping_address: Address
    billing_address: Address
    subtotal: int
    tax_amount: int
    shipping_fee: int
    grand_total: int
    status: OrderStatus
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True, 
        populate_by_name=True
    )
    
class OrderUpdateStatusRequest(BaseModel):
    status: OrderStatus = Field(..., description="The new status to apply to the order")