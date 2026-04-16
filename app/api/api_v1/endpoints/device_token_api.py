from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.device_token_schema import DeviceTokenRegister
from app.services.device_token_services import DeviceTokenService
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response

router = APIRouter()

@router.post("/", response_model=ApiResponse[None], status_code=status.HTTP_201_CREATED)
async def register_device_token(
    data: DeviceTokenRegister,
    current_user: User = Depends(get_current_user)
):
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    await DeviceTokenService.register_token(current_user.id, data)
    return success_response("Device token registered successfully")