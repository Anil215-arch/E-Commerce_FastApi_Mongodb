from fastapi import APIRouter, Depends, HTTPException, Request
from beanie import PydanticObjectId

from app.core.dependencies import get_current_user, _require_user_id
from app.core.i18n import t
from app.core.language_resolver import resolve_user_language
from app.core.message_keys import Msg
from app.core.rate_limiter import user_limiter
from app.models.user_model import User
from app.schemas.cart_schema import CartItemAdd, CartItemUpdate, CartResponse
from app.schemas.common_schema import ApiResponse
from app.services.cart_services import (
    CartService,
    CartLimitExceeded,
    StockExceeded,
    ProductUnavailable,
    VariantNotFound,
    CartConflictError,
    CartError,
)
from app.utils.responses import success_response


router = APIRouter()


@router.get("", response_model=ApiResponse[CartResponse])
@user_limiter.limit("60/minute")
async def get_cart(request: Request, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    language = resolve_user_language(current_user, request)
    cart_data = await CartService.get_cart(user_id, language=language)
    return success_response(t(request, Msg.CART_FETCHED_SUCCESSFULLY, language=language), cart_data)


@router.post("/items", response_model=ApiResponse)
@user_limiter.limit("30/minute")
async def add_item(request: Request, data: CartItemAdd, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    language = resolve_user_language(current_user, request)
    try:
        await CartService.add_to_cart(user_id, data)
        return success_response(t(request, Msg.ITEM_ADDED_TO_CART, language=language))
    except CartConflictError as e:
        raise HTTPException(status_code=409, detail=t(request, e.detail, language=language))
    except (CartLimitExceeded, StockExceeded, ProductUnavailable, VariantNotFound) as e:
        raise HTTPException(status_code=400, detail=t(request, e.detail, language=language))


@router.patch("/items/{product_id}/{sku}", response_model=ApiResponse)
@user_limiter.limit("30/minute")
async def update_quantity(
    request: Request,
    product_id: PydanticObjectId,
    sku: str,
    data: CartItemUpdate,
    current_user: User = Depends(get_current_user),
):
    user_id = _require_user_id(current_user)
    language = resolve_user_language(current_user, request)
    try:
        await CartService.update_item_quantity(user_id, product_id, sku, data)
        return success_response(t(request, Msg.CART_UPDATED, language=language))
    except CartConflictError as e:
        raise HTTPException(status_code=409, detail=t(request, e.detail, language=language))
    except (StockExceeded, VariantNotFound) as e:
        raise HTTPException(status_code=400, detail=t(request, e.detail, language=language))
    except CartError as e:
        raise HTTPException(status_code=404, detail=t(request, e.detail, language=language))


@router.delete("/items/{product_id}/{sku}", response_model=ApiResponse)
@user_limiter.limit("30/minute")
async def remove_item(
    request: Request,
    product_id: PydanticObjectId,
    sku: str,
    current_user: User = Depends(get_current_user),
):
    user_id = _require_user_id(current_user)
    language = resolve_user_language(current_user, request)
    try:
        await CartService.remove_from_cart(user_id, product_id, sku)
        return success_response(t(request, Msg.ITEM_REMOVED, language=language))
    except CartConflictError as e:
        raise HTTPException(status_code=409, detail=t(request, e.detail, language=language))
    except CartError as e:
        raise HTTPException(status_code=404, detail=t(request, e.detail, language=language))
