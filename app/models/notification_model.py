from enum import Enum
from typing import Dict, Any
from beanie import PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.base_model import AuditDocument

class NotificationType(str, Enum):
    ORDER = "ORDER"
    PAYMENT = "PAYMENT"
    SYSTEM = "SYSTEM"
    PROMOTION = "PROMOTION"

class Notification(AuditDocument):
    user_id: PydanticObjectId
    title: str = Field(..., max_length=150)
    message: str = Field(..., max_length=1000)
    type: NotificationType
    is_read: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "notifications"
        indexes = [
            IndexModel(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="user_notification_feed"
            ),
            IndexModel(
                [("user_id", ASCENDING), ("is_read", ASCENDING)],
                name="user_unread_lookup"
            )
        ]