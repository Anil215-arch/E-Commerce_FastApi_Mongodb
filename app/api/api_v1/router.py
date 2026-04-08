from fastapi import APIRouter
from app.api.api_v1.endpoints import product_api, category_api, user_api

api_router = APIRouter()

# Combine all your endpoints here
api_router.include_router(user_api.router, prefix="/users", tags=["Users"])
api_router.include_router(product_api.router, prefix="/products", tags=["Products"])
api_router.include_router(category_api.router, prefix="/categories", tags=["Categories"])