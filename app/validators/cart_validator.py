from app.core.exceptions import DomainValidationError

class CartDomainValidator:
    MAX_QUANTITY_PER_ITEM = 10  # Set this to whatever makes sense for your business

    @staticmethod
    def validate_anti_hoarding(quantity: int) -> None:
        """Prevents users from monopolizing inventory in a single request."""
        if quantity > CartDomainValidator.MAX_QUANTITY_PER_ITEM:
            raise DomainValidationError(
                f"You cannot add more than {CartDomainValidator.MAX_QUANTITY_PER_ITEM} units of a single item to your cart."
            )