from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId

from app.core.exceptions import DomainValidationError
from app.models.notification_model import NotificationType
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


@pytest.mark.asyncio
async def test_create_notification_normalizes_payload_and_sends_pushes():
    user_id = PydanticObjectId()
    insert_mock = AsyncMock()
    notification_doc = SimpleNamespace(
        insert=insert_mock,
        title="Order Update",
        message="Your order is shipped",
        translations={},
        type=NotificationType.ORDER,
        is_read=False,
        metadata={"orderId": "ORD-1"},
        created_at=None,
        id=PydanticObjectId(),
    )
    tokens_cursor = SimpleNamespace(
        to_list=AsyncMock(
            return_value=[
                SimpleNamespace(token="token-1"),
                SimpleNamespace(token="token-2"),
            ]
        )
    )

    with patch("app.services.notification_services.Notification", return_value=notification_doc):
        with patch("app.services.notification_services.DeviceToken.find", return_value=tokens_cursor):
            with patch.object(
                NotificationService,
                "_get_user_preferred_language",
                new=AsyncMock(return_value=None),
            ):
                with patch("app.services.notification_services.PushProvider.send_push", new=AsyncMock()) as mock_send:
                    result = await NotificationService.create_notification(
                        user_id=user_id,
                        title="  Order Update  ",
                        message="  Your order is shipped  ",
                        notification_type=NotificationType.ORDER,
                        metadata={"orderId": "ORD-1"},
                    )

    assert result is notification_doc
    insert_mock.assert_awaited_once()
    assert mock_send.await_count == 2


@pytest.mark.asyncio
async def test_create_notification_rejects_malicious_metadata_key():
    with pytest.raises(DomainValidationError) as exc:
        await NotificationService.create_notification(
            user_id=PydanticObjectId(),
            title="Order Update",
            message="Message",
            notification_type=NotificationType.ORDER,
            metadata={"$where": "evil"},
        )

    assert "cannot start with '$'" in str(exc.value)
