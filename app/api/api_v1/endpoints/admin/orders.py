from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.order_schema import OrderResponse, OrderUpdateStatusRequest, OrderCancelRequest
from app.schemas.common_schema import ApiResponse
from app.services.order_services import OrderService
from app.utils.responses import success_response

router = APIRouter()

@router.patch("/{order_id}/status", response_model=ApiResponse[OrderResponse], status_code=status.HTTP_200_OK)
async def update_order_status_as_admin(order_id: PydanticObjectId, data: OrderUpdateStatusRequest, current_user: User = Depends(get_current_user)):
    """
    Admin Intervention: Override fulfillment status for any order.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user id is missing")
        
    updated_order = await OrderService.update_order_status(order_id, data, current_user)
    return success_response("Order status updated successfully by Admin", updated_order)

@router.patch("/{order_id}/cancel", response_model=ApiResponse[OrderResponse], status_code=status.HTTP_200_OK)
async def cancel_order_as_admin(order_id: PydanticObjectId, data: OrderCancelRequest, current_user: User = Depends(get_current_user)):
    """
    Admin Intervention: Force cancel any order and process refunds.
    """
    cancelled_order = await OrderService.cancel_order(order_id, current_user, data.reason)
    return success_response("Order cancelled successfully by Admin", cancelled_order)