from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from beanie import PydanticObjectId
from typing import List
from app.core.i18n import t
from app.core.message_keys import Msg
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.product_schema import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.product_variant_schema import ProductVariantCreate, ProductVariantUpdate
from app.schemas.common_schema import ApiResponse
from app.services.product_services import ProductService
from app.utils.responses import success_response

router = APIRouter()


@router.post("/", response_model=ApiResponse[ProductResponse], status_code=status.HTTP_201_CREATED)
@user_limiter.limit("5/minute")
async def create_product(request: Request,product: ProductCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    created_product = await ProductService.create_product(product, user_id)
    return success_response(t(request, Msg.PRODUCT_CREATED_SUCCESSFULLY), created_product)

@router.patch("/{id}/images", response_model=ApiResponse[ProductResponse])
@user_limiter.limit("10/minute")
async def upload_images(request: Request, id: PydanticObjectId, images: List[UploadFile] = File(...), current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated = await ProductService.upload_product_images(id, images, user_id)
    if not updated: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.PRODUCT_NOT_FOUND))
    return success_response(t(request, Msg.IMAGES_UPLOADED_SUCCESSFULLY), updated)

@router.patch("/{id}", response_model=ApiResponse[ProductResponse])
@user_limiter.limit("10/minute")
async def update_product(request: Request, id: PydanticObjectId, product: ProductUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated = await ProductService.update_product(id, product, user_id)
    if not updated: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.PRODUCT_NOT_FOUND))
    return success_response(t(request, Msg.PRODUCT_UPDATED_SUCCESSFULLY), updated)

@router.post("/{id}/variants", response_model=ApiResponse[ProductResponse])
@user_limiter.limit("10/minute")
async def add_variant(request: Request, id: PydanticObjectId, variant: ProductVariantCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated_product = await ProductService.add_variant(id, variant, user_id)
    return success_response(t(request, Msg.VARIANT_ADDED_SUCCESSFULLY), updated_product)

@router.patch("/{id}/variants/{sku}", response_model=ApiResponse[ProductResponse])
@user_limiter.limit("10/minute")
async def update_variant(request: Request, id: PydanticObjectId, sku: str, variant: ProductVariantUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated_product = await ProductService.update_variant(id, sku, variant, user_id)
    return success_response(t(request, Msg.VARIANT_UPDATED_SUCCESSFULLY), updated_product)

@router.delete("/{id}/variants/{sku}", response_model=ApiResponse[ProductResponse])
@user_limiter.limit("10/minute")
async def delete_variant(request: Request, id: PydanticObjectId, sku: str, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated_product = await ProductService.delete_variant(id, sku, user_id)
    return success_response(t(request, Msg.VARIANT_DELETED_SUCCESSFULLY), updated_product)

@router.delete("/{id}", response_model=ApiResponse[None])
@user_limiter.limit("10/minute")
async def delete_product(request: Request, id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    if not await ProductService.delete_product(id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.PRODUCT_NOT_FOUND))
    return success_response(t(request, Msg.PRODUCT_DELETED_SUCCESSFULLY))