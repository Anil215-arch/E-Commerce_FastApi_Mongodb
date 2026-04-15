from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from beanie import PydanticObjectId

from app.models.order_model import OrderItemSnapshot
from app.schemas.address_schema import Address
from app.models.transaction_model import PaymentMethod


class InvoiceResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    invoice_number: str
    order_id: PydanticObjectId
    transaction_id: PydanticObjectId
    user_id: PydanticObjectId
    
    items: list[OrderItemSnapshot]
    shipping_address: Address
    billing_address: Address
    
    subtotal: int
    tax_amount: int
    shipping_fee: int
    grand_total: int
    
    currency: str
    payment_method: PaymentMethod
    gateway_transaction_id: Optional[str] = None
    
    issued_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )