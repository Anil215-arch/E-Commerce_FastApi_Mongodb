from app.core.exceptions import DomainValidationError
from app.models.order_model import OrderItemSnapshot

class InvoiceDomainValidator:

    @staticmethod
    def validate_financial_math(subtotal: int, tax: int, shipping: int, grand_total: int) -> None:
        """Ensures the invoice line items and totals are mathematically perfect."""
        if subtotal < 0 or tax < 0 or shipping < 0:
            raise DomainValidationError("Invoice financial values cannot be negative.")
            
        expected_total = subtotal + tax + shipping
        if grand_total != expected_total:
            raise DomainValidationError(
                f"Invoice math mismatch. Expected {expected_total}, but got {grand_total}. Refusing to generate invalid ledger entry."
            )

    @staticmethod
    def validate_transaction_coverage(invoice_total: int, transaction_amount: int) -> None:
        """Ensures the invoice total does not exceed the captured payment amount."""
        if transaction_amount <= 0:
            raise DomainValidationError("Transaction amount must be greater than zero.")
        
        if invoice_total > transaction_amount:
            raise DomainValidationError(
                f"Fraud/Logic prevention: Invoice total ({invoice_total}) exceeds backing transaction amount ({transaction_amount})."
            )
        
    
    @staticmethod
    def validate_items(items: list[OrderItemSnapshot]) -> None:
        if not items:
            raise DomainValidationError("Invoice must contain at least one item.")

        for item in items:
            if item.quantity <= 0:
                raise DomainValidationError("Invalid item quantity in invoice.")
            if item.purchase_price < 0:
                raise DomainValidationError("Invalid item price in invoice.")