from enum import Enum
from beanie import PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.models.base_model import AuditDocument

class DevicePlatform(str, Enum):
    IOS = "IOS"
    ANDROID = "ANDROID"
    WEB = "WEB"
    UNKNOWN = "UNKNOWN"

class DeviceToken(AuditDocument):
    user_id: PydanticObjectId
    token: str = Field(..., min_length=10)
    platform: DevicePlatform = Field(default=DevicePlatform.UNKNOWN)

    class Settings:
        name = "device_tokens"
        indexes = [
            IndexModel(
                [("token", ASCENDING)],
                unique=True,
                name="unique_device_token"
            ),
            IndexModel(
                [("user_id", ASCENDING)],
                name="user_device_tokens"
            )
        ]