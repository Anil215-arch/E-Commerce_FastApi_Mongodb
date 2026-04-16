import asyncio
from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId

from app.models.notification_model import Notification, NotificationType
from app.models.device_token_model import DeviceToken
from app.push.push_provider import PushProvider

class NotificationService:

    @staticmethod
    async def create_notification(
        user_id: PydanticObjectId,
        title: str,
        message: str,
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Notification:
        
        # 1. Persist the database record
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            metadata=metadata or {},
            created_by=user_id,
            updated_by=user_id
        )
        await notification.insert()

        # 2. Fetch active routing destinations
        device_tokens = await DeviceToken.find({
            "user_id": user_id,
            "is_deleted": {"$ne": True}
        }).to_list()

        if not device_tokens:
            return notification

        # 3. Fire pushes concurrently. 'return_exceptions=True' prevents a single failure from failing the batch.
        push_tasks = [
            PushProvider.send_push(
                token=device.token,
                title=title,
                body=message,
                data=metadata
            ) for device in device_tokens
        ]
        await asyncio.gather(*push_tasks, return_exceptions=True)

        return notification

    @staticmethod
    async def get_user_notifications(user_id: PydanticObjectId, limit: int = 50) -> List[Notification]:
        return await Notification.find({
            "user_id": user_id,
            "is_deleted": {"$ne": True}
        }).sort("-created_at").limit(limit).to_list()

    @staticmethod
    async def mark_as_read(notification_id: PydanticObjectId, user_id: PydanticObjectId) -> Notification:
        notification = await Notification.find_one({
            "_id": notification_id,
            "user_id": user_id,
            "is_deleted": {"$ne": True}
        })

        if not notification:
            raise ValueError("Notification not found")

        if not notification.is_read:
            notification.is_read = True
            notification.updated_by = user_id
            await notification.save()

        return notification