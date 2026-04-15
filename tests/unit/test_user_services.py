from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from fastapi import HTTPException

from app.schemas.user_schema import UserTokenData, UserUpdatePassword
from app.services import user_services
from app.services.user_services import UserServices


@pytest.mark.asyncio
async def test_update_user_password_validates_session_before_saving(monkeypatch):
    current_user = SimpleNamespace(
        email="user@example.com",
        hashed_password="stored-hash",
        save=AsyncMock(),
    )
    payload = UserUpdatePassword(
        old_password="OldPass123!",
        new_password="NewPass456@",
        refresh_token="bad-refresh-token",
    )

    monkeypatch.setattr(user_services, "verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(user_services, "get_password_hash", lambda password: f"hashed::{password}")

    async def fail_session_validation(*_args, **_kwargs):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    revoke_mock = AsyncMock()
    monkeypatch.setattr(UserServices, "_validate_session_tokens", fail_session_validation)
    monkeypatch.setattr(UserServices, "_revoke_token", revoke_mock)

    with pytest.raises(HTTPException) as exc_info:
        await UserServices.update_user_password(current_user, "access-token", payload)

    assert exc_info.value.status_code == 401
    assert current_user.hashed_password == "stored-hash"
    current_user.save.assert_not_awaited()
    revoke_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_password_saves_then_revokes_session_tokens(monkeypatch):
    current_user = SimpleNamespace(
        email="user@example.com",
        hashed_password="stored-hash",
        save=AsyncMock(),
    )
    payload = UserUpdatePassword(
        old_password="OldPass123!",
        new_password="NewPass456@",
        refresh_token="refresh-token",
    )
    access_token_data = UserTokenData(sub="user@example.com", token_type="access", jti="access-jti")
    refresh_token_data = UserTokenData(sub="user@example.com", token_type="refresh", jti="refresh-jti")
    access_expires_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
    refresh_expires_at = datetime(2030, 1, 2, tzinfo=timezone.utc)

    monkeypatch.setattr(user_services, "verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(user_services, "get_password_hash", lambda password: f"hashed::{password}")

    async def ok_session_validation(*_args, **_kwargs):
        return access_token_data, access_expires_at, refresh_token_data, refresh_expires_at

    revoke_mock = AsyncMock()
    monkeypatch.setattr(UserServices, "_validate_session_tokens", ok_session_validation)
    monkeypatch.setattr(UserServices, "_revoke_token", revoke_mock)

    await UserServices.update_user_password(current_user, "access-token", payload)

    assert current_user.hashed_password == "hashed::NewPass456@"
    current_user.save.assert_awaited_once()
    assert revoke_mock.await_args_list == [
        call(access_token_data, access_expires_at),
        call(refresh_token_data, refresh_expires_at),
    ]
