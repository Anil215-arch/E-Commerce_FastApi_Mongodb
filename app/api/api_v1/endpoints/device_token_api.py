from fastapi import APIRouter, Depends, Request, status
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.device_token_schema import DeviceTokenRegister
from app.services.device_token_services import DeviceTokenService
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.core.i18n import t
from app.core.language_resolver import resolve_user_language
from app.core.message_keys import Msg

router = APIRouter()

@router.post("", response_model=ApiResponse[None], status_code=status.HTTP_201_CREATED)
@user_limiter.limit("10/minute")
async def register_device_token(request: Request, data: DeviceTokenRegister, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    language = resolve_user_language(current_user, request)
    await DeviceTokenService.register_token(user_id, data)
    return success_response(t(request, Msg.DEVICE_TOKEN_REGISTERED_SUCCESSFULLY, language=language))
