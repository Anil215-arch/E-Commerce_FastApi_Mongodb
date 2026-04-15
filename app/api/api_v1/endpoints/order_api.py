from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, status
from typing import List
from app.core.dependencies import RoleChecker, get_current_user
from app.core.user_role import UserRole
from app.models.user_model import User
from app.schemas.common_schema import ApiResponse
from app.schemas.order_schema import CheckoutRequest, OrderResponse, OrderUpdateStatusRequest
from app.services.order_services import OrderService
from app.utils.responses import success_response

router = APIRouter()

@router.post("/checkout", response_model=ApiResponse[OrderResponse], status_code=status.HTTP_201_CREATED)
async def process_checkout(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Converts the current user's cart into a finalized order.
    Requires shipping and billing addresses in the request body.
    """
    if current_user.id is None:
        raise ValueError("User ID is required")
    order = await OrderService.checkout(current_user.id, data)
    return success_response("Order placed successfully", order)

@router.get("/", response_model=ApiResponse[List[OrderResponse]])
async def get_my_orders(current_user: User = Depends(get_current_user)):
    """
    Returns a list of all orders placed by the authenticated user.
    """
    if current_user.id is None:
        raise ValueError("User ID is required")
    
    orders = await OrderService.get_my_orders(current_user.id)
    return success_response("Order history fetched successfully", orders)


@router.get("/{order_id}", response_model=ApiResponse[OrderResponse])
async def get_order_details(
    order_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    """
    Returns the specific details of a single order.
    """
    if current_user.id is None:
        raise ValueError("User ID is required")

    order = await OrderService.get_order_by_id(current_user.id, order_id)
    return success_response("Order details fetched successfully", order)

@router.patch("/{order_id}/status", response_model=ApiResponse[OrderResponse])
async def update_order_status(
    order_id: PydanticObjectId,
    data: OrderUpdateStatusRequest,
    current_user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.SELLER]))
):
    """
    Updates the fulfillment status of an order. 
    Admins have global access; Sellers are restricted to their own items.
    """
    
    order = await OrderService.update_order_status(order_id, data, current_user)
    return success_response("Order status updated successfully", order)