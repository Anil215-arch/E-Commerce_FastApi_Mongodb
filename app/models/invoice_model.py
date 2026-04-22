from datetime import datetime, timezone
from typing import Optional
from beanie import PydanticObjectId
from pydantic import Field, model_validator
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
    
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    from pydantic import model_validator

    @model_validator(mode="after")
    def validate_invoice_integrity(self):
        # 1. Items must exist
        if not self.items:
            raise ValueError("Invoice must contain at least one item")

        # 2. Line item math must perfectly match the subtotal
        calculated_subtotal = sum(item.purchase_price * item.quantity for item in self.items)
        if self.subtotal != calculated_subtotal:
            raise ValueError(f"Subtotal mismatch: line items sum to {calculated_subtotal}, but subtotal is {self.subtotal}")

        # 3. Financial sanity
        if self.subtotal < 0 or self.tax_amount < 0 or self.shipping_fee < 0:
            raise ValueError("Financial values cannot be negative")

        expected_total = self.subtotal + self.tax_amount + self.shipping_fee
        if self.grand_total != expected_total:
            raise ValueError("Invoice total mismatch")

        # 4. Currency sanity
        if not self.currency or not self.currency.strip():
            raise ValueError("Currency cannot be empty or whitespace")

        return self

    class Settings:
        name = "invoices"
        indexes = [
            IndexModel([("invoice_number", ASCENDING)], unique=True),
            IndexModel([("order_id", ASCENDING)], unique=True),
            IndexModel([("user_id", ASCENDING), ("issued_at", DESCENDING)]),
        ]