from app.core.exceptions import DomainValidationError

class WishlistDomainValidator:
    MAX_WISHLIST_ITEMS = 100

    @staticmethod
    def validate_capacity(current_count: int) -> None:
        """Enforces a hard limit on wishlist size to prevent OOM DOS attacks during retrieval."""
        if current_count >= WishlistDomainValidator.MAX_WISHLIST_ITEMS:
            raise DomainValidationError(
                f"Wishlist is full. You cannot have more than {WishlistDomainValidator.MAX_WISHLIST_ITEMS} items."
            )
            
    @staticmethod
    def validate_sku(sku: str) -> None:
        if not sku.strip():
            raise DomainValidationError("SKU cannot be empty or whitespace.")
        if len(sku.strip()) < 3 or len(sku.strip()) > 100:
            raise DomainValidationError("SKU length must be between 3 and 100 characters.")