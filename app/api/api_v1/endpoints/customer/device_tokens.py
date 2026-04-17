from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.device_token_schema import DeviceTokenRegister
from app.services.device_token_services import DeviceTokenService
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response

router = APIRouter()


@router.post("/", response_model=ApiResponse[None], status_code=status.HTTP_201_CREATED)
async def register_device_token(data: DeviceTokenRegister, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    await DeviceTokenService.register_token(user_id, data)
    return success_response("Device token registered successfully")