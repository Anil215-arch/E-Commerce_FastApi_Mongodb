from fastapi import HTTPException, status
from pydantic import SecretStr, NameEmail 
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings
from app.models.email_otp_model import OTPPurpose

class EmailService:
    @staticmethod
    def _build_connection_config() -> ConnectionConfig:
        if not settings.MAIL_USERNAME.strip() or not settings.MAIL_PASSWORD.strip() or not settings.MAIL_FROM.strip():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Email service is not configured. Set MAIL_USERNAME, MAIL_PASSWORD and MAIL_FROM in .env",
            )

        return ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=SecretStr(settings.MAIL_PASSWORD),
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_STARTTLS=settings.MAIL_STARTTLS,
            MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
        )

    @staticmethod
    async def send_otp_email(to_email: str, otp_code: str, purpose: OTPPurpose) -> None:
        subject_map = {
            OTPPurpose.REGISTRATION: "Verify your Registration",
            OTPPurpose.PASSWORD_RESET: "Reset your Password"
        }
        subject = subject_map.get(purpose, "Your Verification Code")
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Verification Code</h2>
            <p>You requested a code for {purpose.value}.</p>
            <p>Your 6-digit OTP is: <strong><span style="font-size: 24px; color: #4CAF50;">{otp_code}</span></strong></p>
            <p>This code will expire in 10 minutes. Do not share it with anyone.</p>
        </div>
        """

        message = MessageSchema(
            subject=subject,
            recipients=[NameEmail(email=to_email, name="User")], 
            body=html_content,
            subtype=MessageType.html
        )

        fm = FastMail(EmailService._build_connection_config())
        await fm.send_message(message)