from fastapi import APIRouter
from app.api.api_v1.endpoints import (
    auth_api,
    users_api,
    product_api,
    category_api,
    cart_api,
    order_api,
    review_api,
    inventory_api,
    notification_api,
    device_token_api,
    dashboard_api,
    wishlist_api,
)


api_router = APIRouter()

api_router.include_router(auth_api.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users_api.router, prefix="/users", tags=["Users"])
api_router.include_router(product_api.router, prefix="/products", tags=["Products"])
api_router.include_router(category_api.router, prefix="/categories", tags=["Categories"])
api_router.include_router(cart_api.router, prefix="/cart", tags=["Cart"])
api_router.include_router(order_api.router, prefix="/orders", tags=["Orders"])
api_router.include_router(review_api.router, prefix="/reviews", tags=["Reviews"])
api_router.include_router(inventory_api.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(notification_api.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(device_token_api.router, prefix="/device-tokens", tags=["Device Tokens"])
api_router.include_router(dashboard_api.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(wishlist_api.router, prefix="/wishlist", tags=["Wishlist"])
