from copy import deepcopy
import re
from app.schemas.address_schema import Address
from app.core.exceptions import DomainValidationError

class AddressValidator:
    @staticmethod
    def normalize_and_validate(address: Address) -> Address:
        normalized = deepcopy(address)

        normalized.city = normalized.city.strip()
        normalized.state = normalized.state.strip()
        normalized.country = normalized.country.strip()

        if not re.search(r"[a-zA-Z]", normalized.city):
            raise DomainValidationError("City must contain alphabetic characters")

        if not re.search(r"[a-zA-Z]", normalized.state):
            raise DomainValidationError("State must contain alphabetic characters")

        if not re.search(r"[a-zA-Z]", normalized.country):
            raise DomainValidationError("Country must contain alphabetic characters")

        # Optional domain rules (enable only if required)
        # if normalized.country.lower() != "india":
        #     raise DomainValidationError("Only India supported")

        return normalized