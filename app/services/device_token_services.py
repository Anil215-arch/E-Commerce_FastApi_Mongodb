from beanie import PydanticObjectId
from app.models.device_token_model import DeviceToken
from app.schemas.device_token_schema import DeviceTokenRegister

class DeviceTokenService:

    @staticmethod
    async def register_token(user_id: PydanticObjectId, data: DeviceTokenRegister) -> None:
        existing = await DeviceToken.find_one({"token": data.token})

        if existing:
            # Overwrite ownership if the device changed hands or platforms
            if existing.user_id != user_id or existing.platform != data.platform:
                existing.user_id = user_id
                existing.platform = data.platform
                existing.updated_by = user_id
                await existing.save()
            return

        new_token = DeviceToken(
            user_id=user_id,
            token=data.token,
            platform=data.platform,
            created_by=user_id,
            updated_by=user_id
        )
        await new_token.insert()