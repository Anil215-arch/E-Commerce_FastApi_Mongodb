from fastapi import APIRouter, Depends, HTTPException, status, Request
from beanie import PydanticObjectId
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.order_schema import OrderResponse, OrderUpdateStatusRequest, OrderCancelRequest
from app.schemas.common_schema import ApiResponse
from app.services.order_services import OrderService
from app.utils.responses import success_response
from app.core.i18n import t
from app.core.message_keys import Msg

router = APIRouter()

@router.patch("/{order_id}/status", response_model=ApiResponse[OrderResponse], status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def update_order_status_as_admin(request: Request, order_id: PydanticObjectId, data: OrderUpdateStatusRequest, current_user: User = Depends(get_current_user)):
    """
    Admin Intervention: Override fulfillment status for any order.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=t(request, Msg.AUTHENTICATED_USER_ID_MISSING))
        
    updated_order = await OrderService.update_order_status(order_id, data, current_user)
    return success_response(t(request, Msg.ORDER_STATUS_UPDATED_SUCCESSFULLY_BY_ADMIN), updated_order)

@router.patch("/{order_id}/cancel", response_model=ApiResponse[OrderResponse], status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def cancel_order_as_admin(request: Request, order_id: PydanticObjectId, data: OrderCancelRequest, current_user: User = Depends(get_current_user)):
    """
    Admin Intervention: Force cancel any order and process refunds.
    """
    cancelled_order = await OrderService.cancel_order(order_id, current_user, data.reason)
    return success_response(t(request, Msg.ORDER_CANCELLED_SUCCESSFULLY_BY_ADMIN), cancelled_order)
