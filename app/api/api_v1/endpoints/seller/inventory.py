from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from app.core.rate_limiter import user_limiter
from app.core.dependencies import _require_user_id, get_current_user
from app.core.user_role import UserRole
from app.models.user_model import User
from app.schemas.common_schema import ApiResponse
from app.schemas.inventory_schema import InventoryAdjustRequest, InventoryVariantResponse
from app.services.inventory_services import InventoryService
from app.utils.responses import success_response


router = APIRouter()


@router.get(
    "/products/{product_id}/variants/{sku}",
    response_model=ApiResponse[InventoryVariantResponse],
)
@user_limiter.limit("30/minute")
async def get_variant_inventory(
    request: Request,
    product_id: PydanticObjectId,
    sku: str,
    seller_id: PydanticObjectId | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    actor_user_id = _require_user_id(current_user)
    if current_user.role == UserRole.SELLER:
        target_seller_id = actor_user_id
        if seller_id is not None and seller_id != actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sellers can only access their own inventory.",
            )
    else:
        if seller_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="seller_id query parameter is required for admin inventory access.",
            )
        target_seller_id = seller_id

    data = await InventoryService.get_variant_inventory(
        product_id,
        sku,
        target_seller_id,
    )
    return success_response("Inventory fetched successfully", data)


@router.patch(
    "/products/{product_id}/variants/{sku}",
    response_model=ApiResponse[InventoryVariantResponse],
)
@user_limiter.limit("10/minute")
async def adjust_variant_inventory(
    request: Request,
    product_id: PydanticObjectId,
    sku: str,
    payload: InventoryAdjustRequest,
    seller_id: PydanticObjectId | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    actor_user_id = _require_user_id(current_user)
    if current_user.role == UserRole.SELLER:
        target_seller_id = actor_user_id
        if seller_id is not None and seller_id != actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sellers can only mutate their own inventory.",
            )
    else:
        if seller_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="seller_id query parameter is required for admin inventory mutation.",
            )
        target_seller_id = seller_id

    data = await InventoryService.adjust_available_stock(
        product_id=product_id,
        sku=sku,
        owner_seller_id=target_seller_id,
        actor_user_id=actor_user_id,
        request_id=payload.request_id,
        delta=payload.delta,
        reason=payload.reason,
    )
    return success_response("Inventory updated successfully", data)
