from beanie import PydanticObjectId
from app.models.device_token_model import DeviceToken
from app.schemas.device_token_schema import DeviceTokenRegister
from app.validators.device_token_validator import DeviceTokenDomainValidator

class DeviceTokenService:

    @staticmethod
    async def register_token(user_id: PydanticObjectId, data: DeviceTokenRegister) -> None:
        clean_token = DeviceTokenDomainValidator.validate_token_format(data.token)
        existing = await DeviceToken.find_one({"token": clean_token})

        if existing:
            # Overwrite ownership if the device changed hands or platforms
            if existing.user_id != user_id or existing.platform != data.platform:
                existing.user_id = user_id
                existing.platform = data.platform
                existing.updated_by = user_id
                await existing.save()
            return
        current_count = await DeviceToken.find({"user_id": user_id}).count()
        DeviceTokenDomainValidator.validate_device_limit(current_count)
        new_token = DeviceToken(
            user_id=user_id,
            token=clean_token,
            platform=data.platform,
            created_by=user_id,
            updated_by=user_id
        )
        await new_token.insert()