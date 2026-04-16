from fastapi import APIRouter
from app.api.api_v1.endpoints import email_otp_api, order_api, product_api, category_api, review_rating_api, user_api, cart_api

api_router = APIRouter()

# Combine all your endpoints here
api_router.include_router(user_api.router, prefix="/users", tags=["Users"])
api_router.include_router(product_api.router, prefix="/products", tags=["Products"])
api_router.include_router(category_api.router, prefix="/categories", tags=["Categories"])
api_router.include_router(cart_api.router, prefix="/cart", tags=["Cart"])
api_router.include_router(email_otp_api.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(order_api.router, prefix="/orders", tags=["Orders"])
api_router.include_router(review_rating_api.router, tags=["Reviews & Ratings"])