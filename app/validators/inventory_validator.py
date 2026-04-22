from app.core.exceptions import DomainValidationError
import re

class InventoryDomainValidator:
    # Hard ceiling to prevent integer overflow or absurd database states
    MAX_ALLOWED_STOCK = 1_000_000

    @staticmethod
    def validate_operation_quantity(quantity: int) -> None:
        """Ensures internal stock operations use strictly positive integers, preventing math inversion."""
        if quantity <= 0:
            raise DomainValidationError(f"Inventory operation quantity must be strictly positive, got {quantity}.")

    @staticmethod
    def validate_stock_ceiling(new_stock: int) -> None:
        """Prevents stock inflation beyond absolute business limits."""
        if new_stock > InventoryDomainValidator.MAX_ALLOWED_STOCK:
            raise DomainValidationError(
                f"Inventory update rejected. Stock cannot exceed {InventoryDomainValidator.MAX_ALLOWED_STOCK} units."
            )
    
    @staticmethod
    def validate_request_id(request_id: str) -> None:
        if not request_id or len(request_id) < 8:
            raise DomainValidationError("Invalid request_id length")

        if not request_id.replace("-", "").replace("_", "").isalnum():
            raise DomainValidationError("Invalid request_id format")

    @staticmethod
    def validate_reason(reason: str) -> None:
        if len(reason.strip()) < 5:
            raise DomainValidationError("Reason too short")

        if len(reason) > 200:
            raise DomainValidationError("Reason too long")

        if reason != reason.strip():
            raise DomainValidationError("Reason must be trimmed")
    
    @staticmethod
    def validate_sku(sku: str) -> None:
        if sku != sku.strip():
            raise DomainValidationError("SKU must not have leading or trailing spaces")
        
        if not sku or len(sku) > 120:
            raise DomainValidationError("Invalid SKU length")

        if not re.match(r"^[a-zA-Z0-9_-]+$", sku):
            raise DomainValidationError("Invalid SKU format")