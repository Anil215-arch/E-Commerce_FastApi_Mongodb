from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from beanie import PydanticObjectId
from typing import List
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.notification_schema import NotificationResponse, UnreadNotificationCount
from app.services.notification_services import NotificationService
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.core.i18n import get_language, t
from app.core.message_keys import Msg

router = APIRouter()


@router.get("", response_model=ApiResponse[List[NotificationResponse]], status_code=status.HTTP_200_OK)
@user_limiter.limit("60/minute")
async def get_notifications(request: Request, limit: int = Query(50, ge=1, le=100), current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    notifications = await NotificationService.get_user_notifications(user_id, limit)
    language = getattr(current_user, "preferred_language", None) or get_language(request)
    items = [
        NotificationResponse.model_validate(
            NotificationService.serialize_notification(n, language=language)
        )
        for n in notifications
    ]
    return success_response(
        t(request, Msg.NOTIFICATIONS_FETCHED_SUCCESSFULLY, language=language),
        items,
    )


@router.patch("/{notification_id}/read", response_model=ApiResponse[NotificationResponse], status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def mark_notification_read(request: Request, notification_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    try:
        notification = await NotificationService.mark_as_read(notification_id, user_id)
        language = getattr(current_user, "preferred_language", None) or get_language(request)
        return success_response(
            t(request, Msg.NOTIFICATION_MARKED_AS_READ, language=language),
            NotificationResponse.model_validate(
                NotificationService.serialize_notification(
                    notification,
                    language=language,
                )
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/unread-count", response_model=ApiResponse[UnreadNotificationCount], status_code=status.HTTP_200_OK)
@user_limiter.limit("60/minute")
async def get_unread_notification_count(request: Request, current_user: User = Depends(get_current_user)):
    """
    Returns the total count of unread notifications for the authenticated customer.
    """
    user_id = _require_user_id(current_user)
    count = await NotificationService.get_unread_count(user_id)
    language = getattr(current_user, "preferred_language", None) or get_language(request)
    data = UnreadNotificationCount(unread_count=count)
    return success_response(
        t(request, Msg.UNREAD_NOTIFICATION_COUNT_FETCHED_SUCCESSFULLY, language=language),
        data,
    )