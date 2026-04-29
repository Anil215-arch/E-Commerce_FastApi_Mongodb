import asyncio
from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId
from app.validators.notification_validator import NotificationDomainValidator
from app.core.exceptions import DomainValidationError
from app.core.message_keys import Msg
from app.models.notification_model import Notification, NotificationTranslation, NotificationType
from app.models.device_token_model import DeviceToken
from app.core.i18n import CONTENT_TRANSLATION_LANGUAGES
from app.push.push_provider import PushProvider

class NotificationService:
    @staticmethod
    def _build_translations(
        translations: Optional[Dict[str, Dict[str, str]]],
    ) -> Dict[str, NotificationTranslation]:
        if not translations:
            return {}

        invalid_langs = [
            lang for lang in translations.keys()
            if lang not in CONTENT_TRANSLATION_LANGUAGES
        ]
        if invalid_langs:
            raise DomainValidationError("Invalid translation language key.")

        return {
            lang: NotificationTranslation(
                title=value.get("title", ""),
                message=value.get("message", ""),
            )
            for lang, value in translations.items()
        }
        
    @staticmethod
    async def create_notification(
        user_id: PydanticObjectId,
        title: str,
        message: str,
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]] = None,
        translations: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> Notification:
        clean_title, clean_message = NotificationDomainValidator.validate_text(title, message)
        clean_metadata = NotificationDomainValidator.validate_metadata(metadata)
        clean_translations = NotificationService._build_translations(translations)
        # 1. Persist the database record
        notification = Notification(
            user_id=user_id,
            title=clean_title,
            message=clean_message,
            type=notification_type,
            metadata=clean_metadata,
            translations=clean_translations,
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
                title=clean_title,
                body=clean_message,
                data=clean_metadata
            ) for device in device_tokens
        ]
        await asyncio.gather(*push_tasks, return_exceptions=True)

        return notification

    @staticmethod
    def serialize_notification(
        notification: Notification,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        title = notification.title
        message = notification.message

        if language and language in notification.translations:
            translated = notification.translations[language]
            title = translated.title or title
            message = translated.message or message

        return {
            "_id": notification.id,
            "title": title,
            "message": message,
            "type": notification.type,
            "is_read": notification.is_read,
            "metadata": notification.metadata,
            "created_at": notification.created_at,
        }
        
    @staticmethod
    async def get_user_notifications(user_id: PydanticObjectId, limit: int = 50) -> List[Notification]:
        return await Notification.find({
            "user_id": user_id,
            "is_deleted": {"$ne": True}
        }).sort("-created_at").limit(limit).to_list()
        
    @classmethod
    async def get_unread_count(cls, user_id: PydanticObjectId) -> int:
        return await Notification.find(
            {"user_id": user_id, "is_read": False}
        ).count()

    @staticmethod
    async def mark_as_read(notification_id: PydanticObjectId, user_id: PydanticObjectId) -> Notification:
        notification = await Notification.find_one({
            "_id": notification_id,
            "user_id": user_id,
            "is_deleted": {"$ne": True}
        })

        if not notification:
            raise ValueError(Msg.NOTIFICATION_NOT_FOUND)

        if not notification.is_read:
            notification.is_read = True
            notification.updated_by = user_id
            await notification.save()

        return notification