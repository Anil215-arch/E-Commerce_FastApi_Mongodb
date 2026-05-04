from typing import List
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, status, Request
from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.wishlist_schema import WishlistAddRequest, WishlistPopulatedResponse
from app.schemas.common_schema import ApiResponse
from app.services.wishlist_services import WishlistService
from app.utils.responses import success_response
from app.core.rate_limiter import user_limiter

router = APIRouter()

@router.post("", response_model=ApiResponse[None], status_code=status.HTTP_201_CREATED)
@user_limiter.limit("20/minute")
async def add_to_wishlist(
    request: Request,
    payload: WishlistAddRequest,
    current_user: User = Depends(get_current_user)
):
    """Adds a specific product variant to the user's wishlist."""
    assert current_user.id is not None # SATISFIES PYLANCE
    await WishlistService.add_item(current_user.id, payload.product_id, payload.sku)
    return success_response("Item added to wishlist successfully")

@router.delete("/{product_id}/variants/{sku}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
@user_limiter.limit("20/minute")
async def remove_from_wishlist(
    request: Request,
    product_id: PydanticObjectId, 
    sku: str,
    current_user: User = Depends(get_current_user)
):
    """Removes a specific product variant from the user's wishlist."""
    assert current_user.id is not None # SATISFIES PYLANCE
    await WishlistService.remove_item(current_user.id, product_id, sku)
    return success_response("Item removed from wishlist successfully")

@router.get("", response_model=ApiResponse[List[WishlistPopulatedResponse]], status_code=status.HTTP_200_OK)
@user_limiter.limit("60/minute")
async def get_wishlist(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Retrieves all active items in the user's wishlist."""
    assert current_user.id is not None # SATISFIES PYLANCE
    items = await WishlistService.get_user_wishlist(current_user.id)
    return success_response("Wishlist fetched successfully", items)
