from pydantic import BaseModel, Field
from app.models.device_token_model import DevicePlatform

class DeviceTokenRegister(BaseModel):
    token: str = Field(..., min_length=10, description="The unique push token provided by FCM/APNS")
    platform: DevicePlatform = Field(..., description="The platform of the device (IOS, ANDROID, WEB)")