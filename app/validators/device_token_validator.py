import re
from app.core.exceptions import DomainValidationError

class DeviceTokenDomainValidator:
    MAX_DEVICES_PER_USER = 10
    MAX_TOKEN_LENGTH = 512

    @staticmethod
    def validate_token_format(token: str) -> str:
        """Ensures the token doesn't exceed reasonable limits and contains no whitespace."""
        clean_token = token.strip()
        if len(clean_token) < 10 or len(clean_token) > DeviceTokenDomainValidator.MAX_TOKEN_LENGTH:
            raise DomainValidationError(f"Invalid device token length. Must be between 10 and {DeviceTokenDomainValidator.MAX_TOKEN_LENGTH} characters.")
        
        if bool(re.search(r"\s", clean_token)):
            raise DomainValidationError("Device token cannot contain whitespace.")
            
        return clean_token

    @staticmethod
    def validate_device_limit(current_device_count: int) -> None:
        """Prevents notification queue flooding attacks."""
        if current_device_count >= DeviceTokenDomainValidator.MAX_DEVICES_PER_USER:
            raise DomainValidationError(
                f"Maximum device limit reached. You cannot register more than {DeviceTokenDomainValidator.MAX_DEVICES_PER_USER} devices."
            )