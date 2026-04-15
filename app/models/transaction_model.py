from enum import Enum
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.base_model import AuditDocument


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, Enum):
    CARD = "CARD"
    UPI = "UPI"


class TransactionAllocation(BaseModel):
    order_id: PydanticObjectId
    seller_id: PydanticObjectId
    amount: int = Field(..., ge=0)
    refunded_amount: int = Field(default=0, ge=0)


class Transaction(AuditDocument):
    user_id: PydanticObjectId
    checkout_batch_id: str

    amount: int = Field(..., ge=0)
    refunded_amount: int = Field(default=0, ge=0)

    status: TransactionStatus = Field(default=TransactionStatus.PENDING)
    payment_method: PaymentMethod
    gateway_transaction_id: Optional[str] = None

    allocations: List[TransactionAllocation] = Field(default_factory=list)

    class Settings:
        name = "transactions"
        indexes = [
            IndexModel(
                [("checkout_batch_id", ASCENDING)],
                unique=True,
                partialFilterExpression={"status": "SUCCESS"},
                name="unique_successful_batch",
            ),
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel(
                [("gateway_transaction_id", ASCENDING)], 
                unique=True, 
                partialFilterExpression={"gateway_transaction_id": {"$type": "string"}},
                name="unique_gateway_id"
            ),
        ]
