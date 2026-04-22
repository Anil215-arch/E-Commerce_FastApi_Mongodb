from datetime import datetime, timezone
from app.core.exceptions import DomainValidationError

class OTPDomainValidator:
    MAX_VERIFICATION_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = 60

    @staticmethod
    def validate_cooldown(created_at: datetime) -> None:
        """Prevents email spam and API budget draining attacks."""
        seconds_since_creation = (datetime.now(timezone.utc) - created_at).total_seconds()
        if seconds_since_creation < OTPDomainValidator.RESEND_COOLDOWN_SECONDS:
            remaining = int(OTPDomainValidator.RESEND_COOLDOWN_SECONDS - seconds_since_creation)
            raise DomainValidationError(
                f"Please wait {remaining} seconds before requesting a new OTP."
            )

    @staticmethod
    def validate_attempts(current_attempts: int) -> None:
        """Prevents brute-force attacks on the 6-digit PIN."""
        if current_attempts >= OTPDomainValidator.MAX_VERIFICATION_ATTEMPTS:
            raise DomainValidationError(
                "Maximum verification attempts exceeded. This OTP has been invalidated for security. Please request a new one."
            )
    
    @staticmethod
    def validate_otp_code_format(otp_code: str) -> None:
        if not otp_code or len(otp_code) != 6 or not otp_code.isdigit():
            raise DomainValidationError("OTP code must be exactly 6 digits.")