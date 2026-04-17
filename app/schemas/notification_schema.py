from datetime import datetime
from typing import Dict, Any
from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.notification_model import NotificationType

class NotificationResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    title: str
    message: str
    type: NotificationType
    is_read: bool
    metadata: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
    
class UnreadNotificationCount(BaseModel):
    unread_count: int