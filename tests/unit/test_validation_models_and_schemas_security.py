from datetime import datetime, timedelta, timezone

import pytest
from beanie import PydanticObjectId

from app.models.counter_model import Counter
from app.models.device_token_model import DevicePlatform, DeviceToken
from app.models.email_otp_model import EmailOTPVerification, OTPPurpose
from app.models.notification_model import Notification, NotificationType
from app.models.revoked_token_model import RevokedToken
from app.schemas.device_token_schema import DeviceTokenRegister
from app.schemas.email_otp_schema import ResetPasswordRequest, VerifyOTPRequest


def test_counter_model_rejects_negative_seq():
    with pytest.raises(ValueError, match="cannot be negative"):
        Counter(key="invoice_2026", seq=-1)


def test_counter_model_rejects_whitespace_key():
    with pytest.raises(ValueError, match="cannot be empty"):
        Counter(key="   ", seq=1)


def test_device_token_model_rejects_leading_trailing_spaces():
    with pytest.raises(ValueError, match="leading or trailing spaces"):
        DeviceToken(
            user_id=PydanticObjectId(),
            token=" token-with-space ",
            platform=DevicePlatform.ANDROID,
        )


def test_email_otp_model_rejects_expires_before_created():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="must be later than"):
        EmailOTPVerification(
            email="user@example.com",
            hashed_otp="x" * 20,
            purpose=OTPPurpose.REGISTRATION,
            created_at=now,
            expires_at=now - timedelta(minutes=1),
        )


def test_notification_model_rejects_blank_title():
    with pytest.raises(ValueError, match="title cannot be empty"):
        Notification(
            user_id=PydanticObjectId(),
            title="   ",
            message="msg",
            type=NotificationType.SYSTEM,
        )


def test_revoked_token_model_rejects_blank_jti():
    with pytest.raises(ValueError, match="jti cannot be empty"):
        RevokedToken(
            jti="   ",
            token_type="refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )


def test_device_token_schema_trims_token():
    payload = DeviceTokenRegister(token="   abcdefghij   ", platform=DevicePlatform.WEB)
    assert payload.token == "abcdefghij"


def test_verify_otp_schema_rejects_non_digits():
    with pytest.raises(Exception):
        VerifyOTPRequest(email="user@example.com", otp_code="12ab56")


def test_reset_password_schema_rejects_whitespace_password():
    with pytest.raises(Exception):
        ResetPasswordRequest(
            email="user@example.com",
            otp_code="123456",
            new_password="    ",
        )
