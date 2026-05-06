from copy import deepcopy

from app.schemas.address_schema import Address
from app.core.exceptions import DomainValidationError


class AddressValidator:
    @staticmethod
    def _contains_letter(value: str) -> bool:
        return any(char.isalpha() for char in value)

    @staticmethod
    def normalize_and_validate(address: Address) -> Address:
        normalized = deepcopy(address)

        normalized.city = normalized.city.strip()
        normalized.state = normalized.state.strip()
        normalized.country = normalized.country.strip()

        if not AddressValidator._contains_letter(normalized.city):
            raise DomainValidationError("City must contain alphabetic characters")

        if not AddressValidator._contains_letter(normalized.state):
            raise DomainValidationError("State must contain alphabetic characters")

        if not AddressValidator._contains_letter(normalized.country):
            raise DomainValidationError("Country must contain alphabetic characters")

        return normalized