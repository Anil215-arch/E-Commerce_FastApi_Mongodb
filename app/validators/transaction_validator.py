from typing import List
from app.core.exceptions import DomainValidationError
from app.models.order_model import OrderItemSnapshot
from app.models.transaction_model import TransactionAllocation

class TransactionDomainValidator:
    
    @staticmethod
    def validate_allocations(total_amount: int, allocations: List[TransactionAllocation]) -> None:
        """Ensures the sum of allocated amounts perfectly matches the total transaction charge."""
        if not allocations:
            raise DomainValidationError("Transaction must have at least one allocation.")
            
        allocated_sum = sum(allocation.amount for allocation in allocations)
        if allocated_sum != total_amount:
            raise DomainValidationError(
                f"Ledger imbalance: Transaction amount is {total_amount}, but allocations sum to {allocated_sum}."
            )

    @staticmethod
    def validate_refund_math(total_amount: int, total_refunded: int, allocations: List[TransactionAllocation]) -> None:
        """Ensures refund math aligns across the ledger and does not exceed captured funds."""
        if total_refunded > total_amount:
            raise DomainValidationError("Total refunded amount cannot exceed the original transaction amount.")
            
        refunded_sum = sum(allocation.refunded_amount for allocation in allocations)
        if refunded_sum != total_refunded:
            raise DomainValidationError(
                f"Refund imbalance: Transaction refund is {total_refunded}, but allocations sum to {refunded_sum}."
            )
        
        for alloc in allocations:
            if alloc.refunded_amount > alloc.amount:
                raise DomainValidationError("An allocation refund cannot exceed its original captured amount.")
            
    @staticmethod
    def validate_checkout_items(items: List[OrderItemSnapshot]) -> None:
        for item in items:
            if item.quantity <= 0:
                raise DomainValidationError("Invalid item quantity in checkout.")
            if item.purchase_price < 0:
                raise DomainValidationError("Invalid item price in checkout.")