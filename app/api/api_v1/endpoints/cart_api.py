from fastapi import APIRouter, Depends, status
from beanie import PydanticObjectId
from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.cart_schema import CartItemAdd, CartItemUpdate, CartResponse
from app.schemas.common_schema import ApiResponse
from app.services.cart_services import CartService
from app.utils.responses import success_response

router = APIRouter()

@router.get("/", response_model=ApiResponse[CartResponse])
async def get_cart(current_user: User = Depends(get_current_user)):
    cart_data = await CartService.get_cart(current_user.id)
    return success_response("Cart fetched successfully", cart_data)

@router.post("/items", response_model=ApiResponse)
async def add_item(data: CartItemAdd, current_user: User = Depends(get_current_user)):
    await CartService.add_to_cart(current_user.id, data)
    return success_response("Item added to cart")

@router.patch("/items/{product_id}/{sku}", response_model=ApiResponse)
async def update_quantity(
    product_id: PydanticObjectId, sku: str, data: CartItemUpdate, 
    current_user: User = Depends(get_current_user)
):
    await CartService.update_item_quantity(current_user.id, product_id, sku, data)
    return success_response("Cart updated")

@router.delete("/items/{product_id}/{sku}", response_model=ApiResponse)
async def remove_item(
    product_id: PydanticObjectId, sku: str, 
    current_user: User = Depends(get_current_user)
):
    await CartService.remove_from_cart(current_user.id, product_id, sku)
    return success_response("Item removed")