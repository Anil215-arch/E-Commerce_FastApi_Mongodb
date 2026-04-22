from pydantic import BaseModel, Field, model_validator
from app.models.device_token_model import DevicePlatform

class DeviceTokenRegister(BaseModel):
    token: str = Field(..., min_length=10, max_length=512, description="The unique push token provided by FCM/APNS")
    platform: DevicePlatform = Field(..., description="The platform of the device (IOS, ANDROID, WEB)")
    
    @model_validator(mode="before")
    @classmethod
    def normalize_token(cls, data):
        if isinstance(data, dict) and "token" in data and isinstance(data["token"], str):
            data["token"] = data["token"].strip()
        return data