from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from fastapi import HTTPException
from beanie import PydanticObjectId

from app.schemas.address_schema import Address
from app.schemas.user_schema import UserAddAddress
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


def _address_payload(city: str = "Bengaluru") -> UserAddAddress:
    return UserAddAddress(
        address=Address(
            full_name="John Doe",
            phone_number="9876543210",
            street_address="123 Main Street",
            city=city,
            postal_code="560001",
            state="Karnataka",
            country="India",
        )
    )


@pytest.mark.asyncio
async def test_add_user_address_appends_and_saves(monkeypatch):
    current_user = SimpleNamespace(
        id=PydanticObjectId(),
        addresses=[],
        updated_by=None,
        save=AsyncMock(),
    )
    payload = _address_payload()

    monkeypatch.setattr(
        user_services.UserResponse,
        "model_validate",
        staticmethod(lambda value: value),
    )

    result = await UserServices.add_user_address(current_user, payload)

    assert result is current_user
    assert len(current_user.addresses) == 1
    assert current_user.addresses[0].city == "Bengaluru"
    assert current_user.updated_by == current_user.id
    current_user.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_user_address_rejects_more_than_ten(monkeypatch):
    existing_addresses = [_address_payload(city=f"City{i}").address for i in range(10)]
    current_user = SimpleNamespace(
        id=PydanticObjectId(),
        addresses=existing_addresses,
        updated_by=None,
        save=AsyncMock(),
    )

    monkeypatch.setattr(
        user_services.UserResponse,
        "model_validate",
        staticmethod(lambda value: value),
    )

    with pytest.raises(HTTPException) as exc_info:
        await UserServices.add_user_address(current_user, _address_payload())

    assert exc_info.value.status_code == 400
    assert "maximum of 10 addresses" in str(exc_info.value.detail).lower()
    current_user.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_address_replaces_target_index(monkeypatch):
    current_user = SimpleNamespace(
        id=PydanticObjectId(),
        addresses=[_address_payload(city="Mysuru").address],
        updated_by=None,
        save=AsyncMock(),
    )
    payload = _address_payload(city="Bengaluru")

    monkeypatch.setattr(
        user_services.UserResponse,
        "model_validate",
        staticmethod(lambda value: value),
    )

    result = await UserServices.update_user_address(current_user, 0, payload)

    assert result is current_user
    assert current_user.addresses[0].city == "Bengaluru"
    assert current_user.updated_by == current_user.id
    current_user.save.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("index", [-1, 1])
async def test_update_user_address_rejects_invalid_index(monkeypatch, index):
    current_user = SimpleNamespace(
        id=PydanticObjectId(),
        addresses=[_address_payload().address],
        updated_by=None,
        save=AsyncMock(),
    )

    monkeypatch.setattr(
        user_services.UserResponse,
        "model_validate",
        staticmethod(lambda value: value),
    )

    with pytest.raises(HTTPException) as exc_info:
        await UserServices.update_user_address(current_user, index, _address_payload(city="Hubli"))

    assert exc_info.value.status_code == 404
    assert "address not found" in str(exc_info.value.detail).lower()
    current_user.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_user_address_deletes_target_index(monkeypatch):
    first = _address_payload(city="Mysuru").address
    second = _address_payload(city="Bengaluru").address
    current_user = SimpleNamespace(
        id=PydanticObjectId(),
        addresses=[first, second],
        updated_by=None,
        save=AsyncMock(),
    )

    monkeypatch.setattr(
        user_services.UserResponse,
        "model_validate",
        staticmethod(lambda value: value),
    )

    result = await UserServices.remove_user_address(current_user, 0)

    assert result is current_user
    assert len(current_user.addresses) == 1
    assert current_user.addresses[0].city == "Bengaluru"
    assert current_user.updated_by == current_user.id
    current_user.save.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("index", [-1, 5])
async def test_remove_user_address_rejects_invalid_index(monkeypatch, index):
    current_user = SimpleNamespace(
        id=PydanticObjectId(),
        addresses=[_address_payload().address],
        updated_by=None,
        save=AsyncMock(),
    )

    monkeypatch.setattr(
        user_services.UserResponse,
        "model_validate",
        staticmethod(lambda value: value),
    )

    with pytest.raises(HTTPException) as exc_info:
        await UserServices.remove_user_address(current_user, index)

    assert exc_info.value.status_code == 404
    assert "address not found" in str(exc_info.value.detail).lower()
    current_user.save.assert_not_awaited()
