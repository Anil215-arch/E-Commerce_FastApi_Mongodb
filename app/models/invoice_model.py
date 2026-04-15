from datetime import datetime
from typing import Optional
from beanie import PydanticObjectId
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING
from app.models.base_model import AuditDocument
from app.models.order_model import OrderItemSnapshot
from app.schemas.address_schema import Address
from app.models.transaction_model import PaymentMethod

class Invoice(AuditDocument):
    invoice_number: str = Field(...)
    order_id: PydanticObjectId
    transaction_id: PydanticObjectId
    user_id: PydanticObjectId
    
    # Immutable Snapshots
    items: list[OrderItemSnapshot]
    shipping_address: Address
    billing_address: Address
    
    subtotal: int
    tax_amount: int
    shipping_fee: int
    grand_total: int
    currency: str = Field(default="INR") 
    
    payment_method: PaymentMethod
    gateway_transaction_id: Optional[str] = None
    
    issued_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "invoices"
        indexes = [
            IndexModel([("invoice_number", ASCENDING)], unique=True),
            IndexModel([("order_id", ASCENDING)], unique=True),
            IndexModel([("user_id", ASCENDING), ("issued_at", DESCENDING)]),
        ]