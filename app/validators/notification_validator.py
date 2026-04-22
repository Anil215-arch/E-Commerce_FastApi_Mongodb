from typing import Dict, Any, Optional
from app.core.exceptions import DomainValidationError

class NotificationDomainValidator:
    MAX_METADATA_KEYS = 10
    MAX_TITLE_LENGTH = 150
    MAX_MESSAGE_LENGTH = 1000

    @staticmethod
    def validate_text(title: str, message: str) -> tuple[str, str]:
        """Ensures notifications aren't empty and don't exceed push limits."""
        clean_title = title.strip()
        clean_message = message.strip()

        if not clean_title or not clean_message:
            raise DomainValidationError("Notification title and message cannot be empty or just whitespace.")

        if len(clean_title) > NotificationDomainValidator.MAX_TITLE_LENGTH:
            raise DomainValidationError(f"Title exceeds the {NotificationDomainValidator.MAX_TITLE_LENGTH} character limit.")

        if len(clean_message) > NotificationDomainValidator.MAX_MESSAGE_LENGTH:
            raise DomainValidationError(f"Message exceeds the {NotificationDomainValidator.MAX_MESSAGE_LENGTH} character limit.")

        return clean_title, clean_message

    @staticmethod
    def validate_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sanitizes the metadata payload to prevent NoSQL injection via $ operators 
        and prevents excessive bloat.
        """
        if not metadata:
            return {}

        if len(metadata) > NotificationDomainValidator.MAX_METADATA_KEYS:
            raise DomainValidationError(f"Metadata payload cannot contain more than {NotificationDomainValidator.MAX_METADATA_KEYS} keys.")

        for key in metadata.keys():
            if not isinstance(key, str):
                raise DomainValidationError("Metadata keys must be strings.")
            if key.startswith("$"):
                raise DomainValidationError(f"Security Fault: Metadata keys cannot start with '$'. Invalid key: '{key}'")
            if "." in key:
                raise DomainValidationError(f"Security Fault: Metadata keys cannot contain periods ('.'). Invalid key: '{key}'")

        return metadata