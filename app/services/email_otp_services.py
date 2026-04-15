import random
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from app.models.email_otp_model import EmailOTPVerification, OTPPurpose
from app.utils.email_services import EmailService



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
        
        await EmailOTPVerification.find(
            EmailOTPVerification.email == email,
            EmailOTPVerification.purpose == purpose
        ).delete()

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
        """Verifies the OTP and instantly invalidates it upon success."""
        
        otp_doc = await EmailOTPVerification.find_one(
            EmailOTPVerification.email == email,
            EmailOTPVerification.purpose == purpose
        )

        if not otp_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="OTP not found or has expired"
            )

        expires_at = OTPService._as_utc_aware(otp_doc.expires_at)
        if expires_at < datetime.now(timezone.utc):
            await otp_doc.delete()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="OTP has expired. Please request a new one."
            )

        if not OTPService._verify_otp_hash(otp_code, otp_doc.hashed_otp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid OTP code"
            )

        await otp_doc.delete()
        
        return True