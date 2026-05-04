from fastapi import APIRouter, Depends, HTTPException, Request
from beanie import PydanticObjectId
from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.cart_schema import CartItemAdd, CartItemUpdate, CartResponse
from app.schemas.common_schema import ApiResponse
from app.services.cart_services import (
    CartService, CartLimitExceeded, StockExceeded,
    ProductUnavailable, VariantNotFound, CartConflictError, CartError
)
from app.utils.responses import success_response
from app.core.rate_limiter import user_limiter

router = APIRouter()


@router.get("/", response_model=ApiResponse[CartResponse])
@user_limiter.limit("60/minute")
async def get_cart(request: Request, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    cart_data = await CartService.get_cart(user_id)
    return success_response("Cart fetched successfully", cart_data)


@router.post("/items", response_model=ApiResponse)
@user_limiter.limit("30/minute")
async def add_item(request: Request, data: CartItemAdd, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    try:
        await CartService.add_to_cart(user_id, data)
        return success_response("Item added to cart")
    except CartConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (CartLimitExceeded, StockExceeded, ProductUnavailable, VariantNotFound) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/items/{product_id}/{sku}", response_model=ApiResponse)
@user_limiter.limit("30/minute")
async def update_quantity(request: Request, product_id: PydanticObjectId, sku: str, data: CartItemUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    try:
        await CartService.update_item_quantity(user_id, product_id, sku, data)
        return success_response("Cart updated")
    except CartConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (StockExceeded, VariantNotFound) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CartError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/items/{product_id}/{sku}", response_model=ApiResponse)
@user_limiter.limit("30/minute")
async def remove_item(request: Request, product_id: PydanticObjectId, sku: str, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    try:
        await CartService.remove_from_cart(user_id, product_id, sku)
        return success_response("Item removed")
    except CartConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CartError as e:
        raise HTTPException(status_code=404, detail=str(e))
