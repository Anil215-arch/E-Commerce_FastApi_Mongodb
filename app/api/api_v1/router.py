from fastapi import APIRouter
from app.api.api_v1.endpoints import product_api

api_router = APIRouter()

# Combine all your endpoints here
api_router.include_router(product_api.router, prefix="/products", tags=["Products"])