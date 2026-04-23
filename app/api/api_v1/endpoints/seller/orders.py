from fastapi import APIRouter, Depends, HTTPException, status, Request
from beanie import PydanticObjectId
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.order_schema import OrderResponse, OrderUpdateStatusRequest
from app.schemas.common_schema import ApiResponse
from app.services.order_services import OrderService
from app.utils.responses import success_response

router = APIRouter()

@router.patch("/{order_id}/status", response_model=ApiResponse[OrderResponse])
@user_limiter.limit("10/minute")
async def update_order_status(request: Request, order_id: PydanticObjectId, data: OrderUpdateStatusRequest, current_user: User = Depends(get_current_user)):
    """
    Seller endpoint to update fulfillment status.
    The Service layer must ensure the seller owns the products in this order.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user id is missing")
    
    updated_order = await OrderService.update_order_status(order_id, data, current_user)
    return success_response("Order status updated successfully", updated_order)