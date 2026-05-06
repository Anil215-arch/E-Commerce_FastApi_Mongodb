from datetime import datetime
from typing import Dict, Any
from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field
from app.models.notification_model import NotificationType

class NotificationTranslationSchema(BaseModel):
    title: str = Field(..., max_length=150)
    message: str = Field(..., max_length=1000)

    model_config = ConfigDict(from_attributes=True)
    
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