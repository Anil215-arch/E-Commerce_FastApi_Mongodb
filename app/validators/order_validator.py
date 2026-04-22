from app.core.exceptions import DomainValidationError

class OrderDomainValidator:
    # Set a maximum transaction limit (e.g., $100,000 represented in your base currency/cents)
    # This prevents integer overflow attacks that could crash your payment gateway
    MAX_ORDER_TOTAL = 10_000_000 

    @staticmethod
    def validate_financial_math(subtotal: int, tax: int, shipping: int, grand_total: int) -> None:
        """Ensures order totals mathematically align and prevent overflow manipulation."""
        if subtotal < 0 or tax < 0 or shipping < 0:
            raise DomainValidationError("Financial values cannot be negative.")
            
        expected_total = subtotal + tax + shipping
        if grand_total != expected_total:
            raise DomainValidationError(
                f"Financial math mismatch. Expected {expected_total}, but got {grand_total}."
            )
            
        if grand_total > OrderDomainValidator.MAX_ORDER_TOTAL:
            raise DomainValidationError("Order total exceeds the maximum allowed transaction limit.")

    @staticmethod
    def validate_cancellation_reason(reason: str) -> str:
        """Ensures the audit trail for cancellations is meaningful."""
        clean_reason = reason.strip()
        if not clean_reason:
            raise DomainValidationError("Cancellation reason cannot be empty or whitespace.")
            
        if len(clean_reason) > 500:
            raise DomainValidationError("Cancellation reason exceeds the 500 character limit.")
            
        return clean_reason
    
    @staticmethod
    def validate_checkout_request(
        checkout_batch_id: str,
        shipping_index: int,
        billing_index: int
    ) -> None:
        if not checkout_batch_id.strip():
            raise DomainValidationError("checkout_batch_id cannot be empty")

        if shipping_index < 0 or billing_index < 0:
            raise DomainValidationError("Address index cannot be negative")