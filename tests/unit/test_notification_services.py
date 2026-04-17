from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId

from app.services.notification_services import NotificationService


@pytest.mark.asyncio
async def test_get_unread_count_returns_service_count():
    user_id = PydanticObjectId()
    find_chain = SimpleNamespace(count=AsyncMock(return_value=7))

    with patch("app.services.notification_services.Notification.find", return_value=find_chain) as mock_find:
        unread_count = await NotificationService.get_unread_count(user_id)

    assert unread_count == 7
    mock_find.assert_called_once_with({"user_id": user_id, "is_read": False})
    find_chain.count.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_unread_count_returns_zero_when_no_unread_notifications():
    user_id = PydanticObjectId()
    find_chain = SimpleNamespace(count=AsyncMock(return_value=0))

    with patch("app.services.notification_services.Notification.find", return_value=find_chain):
        unread_count = await NotificationService.get_unread_count(user_id)

    assert unread_count == 0
