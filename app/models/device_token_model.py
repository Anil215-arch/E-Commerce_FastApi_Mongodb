from enum import Enum
from beanie import PydanticObjectId
from pydantic import Field, model_validator
from pymongo import ASCENDING, IndexModel

from app.models.base_model import AuditDocument

class DevicePlatform(str, Enum):
    IOS = "IOS"
    ANDROID = "ANDROID"
    WEB = "WEB"
    UNKNOWN = "UNKNOWN"

class DeviceToken(AuditDocument):
    user_id: PydanticObjectId
    token: str = Field(..., min_length=10, max_length=512)
    platform: DevicePlatform = Field(default=DevicePlatform.UNKNOWN)

    @model_validator(mode="after")
    def validate_device_token(self):
        clean_token = self.token.strip()

        if not clean_token:
            raise ValueError("Device token cannot be empty or whitespace")

        if clean_token != self.token:
            raise ValueError("Device token must not have leading or trailing spaces")

        return self

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