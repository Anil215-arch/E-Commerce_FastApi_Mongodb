from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from beanie import PydanticObjectId

from app.core.exceptions import DomainValidationError
from app.models.device_token_model import DevicePlatform
from app.schemas.device_token_schema import DeviceTokenRegister
from app.services.device_token_services import DeviceTokenService


@pytest.mark.asyncio
async def test_register_token_updates_existing_record_owner_and_platform():
    user_id = PydanticObjectId()
    existing = SimpleNamespace(
        user_id=PydanticObjectId(),
        platform=DevicePlatform.IOS,
        updated_by=None,
        save=AsyncMock(),
    )

    with patch("app.services.device_token_services.DeviceToken.find_one", new=AsyncMock(return_value=existing)):
        await DeviceTokenService.register_token(
            user_id,
            DeviceTokenRegister(token="abcdefghijk", platform=DevicePlatform.ANDROID),
        )

    assert existing.user_id == user_id
    assert existing.platform == DevicePlatform.ANDROID
    assert existing.updated_by == user_id
    existing.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_token_inserts_new_device_when_under_limit():
    user_id = PydanticObjectId()
    inserted = SimpleNamespace(insert=AsyncMock())
    count_cursor = SimpleNamespace(count=AsyncMock(return_value=2))
    device_cls = MagicMock(return_value=inserted)
    device_cls.find_one = AsyncMock(return_value=None)
    device_cls.find = MagicMock(return_value=count_cursor)

    with patch("app.services.device_token_services.DeviceToken", device_cls):
        await DeviceTokenService.register_token(
            user_id,
            DeviceTokenRegister(token="abcdefghijk", platform=DevicePlatform.WEB),
        )

    inserted.insert.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_token_rejects_when_device_limit_reached():
    user_id = PydanticObjectId()
    count_cursor = SimpleNamespace(count=AsyncMock(return_value=10))

    with patch("app.services.device_token_services.DeviceToken.find_one", new=AsyncMock(return_value=None)):
        with patch("app.services.device_token_services.DeviceToken.find", return_value=count_cursor):
            with pytest.raises(DomainValidationError) as exc:
                await DeviceTokenService.register_token(
                    user_id,
                    DeviceTokenRegister(token="abcdefghijk", platform=DevicePlatform.WEB),
                )

    assert "maximum device limit" in str(exc.value).lower()
