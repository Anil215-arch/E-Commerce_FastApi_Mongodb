from fastapi import APIRouter, Depends, HTTPException, status, Query
from beanie import PydanticObjectId
from typing import List

from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.notification_schema import NotificationResponse
from app.services.notification_services import NotificationService
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response

router = APIRouter()

@router.get("/", response_model=ApiResponse[List[NotificationResponse]], status_code=status.HTTP_200_OK)
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    notifications = await NotificationService.get_user_notifications(current_user.id, limit)
    items = [NotificationResponse.model_validate(n) for n in notifications]
    
    return success_response("Notifications fetched successfully", items)

@router.patch("/{notification_id}/read", response_model=ApiResponse[NotificationResponse], status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        notification = await NotificationService.mark_as_read(notification_id, current_user.id)
        return success_response("Notification marked as read", NotificationResponse.model_validate(notification))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))