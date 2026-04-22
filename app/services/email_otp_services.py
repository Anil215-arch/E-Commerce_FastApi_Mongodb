import random
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from app.models.email_otp_model import EmailOTPVerification, OTPPurpose
from app.utils.email_services import EmailService
from app.core.exceptions import DomainValidationError
from app.validators.otp_validator import OTPDomainValidator



otp_hash = PasswordHash.recommended()

class OTPService:
    OTP_EXPIRATION_MINUTES = 10

    @staticmethod
    def _as_utc_aware(dt: datetime) -> datetime:
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _generate_otp_code() -> str:
        return f"{random.randint(100000, 999999)}"

    @staticmethod
    def _hash_otp(otp: str) -> str:
        return otp_hash.hash(otp)

    @staticmethod
    def _verify_otp_hash(plain_otp: str, hashed_otp: str) -> bool:
        return otp_hash.verify(plain_otp, hashed_otp)

    @staticmethod
    async def create_and_send_otp(email: str, purpose: OTPPurpose) -> None:
        """Generates, hashes, stores, and sends an OTP."""
        
        existing_otp = await EmailOTPVerification.find_one(
            EmailOTPVerification.email == email,
            EmailOTPVerification.purpose == purpose
        )
        if existing_otp:
            # Ensure it is UTC aware before comparing
            created_at = OTPService._as_utc_aware(existing_otp.created_at)
            OTPDomainValidator.validate_cooldown(created_at)
            # If cooldown passed, wipe the old one to issue a new one
            await existing_otp.delete()

        raw_otp = OTPService._generate_otp_code()
        hashed_otp = OTPService._hash_otp(raw_otp)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTPService.OTP_EXPIRATION_MINUTES)

        otp_doc = EmailOTPVerification(
            email=email,
            hashed_otp=hashed_otp,
            purpose=purpose,
            expires_at=expires_at
        )
        await otp_doc.insert()

        await EmailService.send_otp_email(to_email=email, otp_code=raw_otp, purpose=purpose)
        
    @staticmethod
    async def verify_otp(email: str, otp_code: str, purpose: OTPPurpose) -> bool:
        """Verifies the OTP, tracking attempts and instantly invalidating upon success or max fails."""
        OTPDomainValidator.validate_otp_code_format(otp_code)
        otp_doc = await EmailOTPVerification.find_one(
            EmailOTPVerification.email == email,
            EmailOTPVerification.purpose == purpose
        )

        if not otp_doc:
            raise DomainValidationError("OTP not found or has expired.")

        # 1. Enforce max attempts
        try:
            OTPDomainValidator.validate_attempts(otp_doc.attempts)
        except DomainValidationError as e:
            await otp_doc.delete() # Nuke the compromised OTP
            raise e

        # 2. Enforce expiration
        expires_at = OTPService._as_utc_aware(otp_doc.expires_at)
        if expires_at < datetime.now(timezone.utc):
            await otp_doc.delete()
            raise DomainValidationError("OTP has expired. Please request a new one.")

        # 3. Verify Hash and Track Fails
        if not OTPService._verify_otp_hash(otp_code, otp_doc.hashed_otp):
            otp_doc.attempts += 1
            await otp_doc.save()
            raise DomainValidationError("Invalid OTP code.")

        # Verification successful, wipe the OTP to prevent reuse
        await otp_doc.delete()
        return True