from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from beanie import PydanticObjectId
from typing import List

from app.services.product_query_services import ProductQueryService
from app.schemas.product_query_schema import ProductQueryParams
from app.schemas.common_schema import PaginatedResponse
from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.product_schema import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.product_variant_schema import ProductVariantCreate, ProductVariantUpdate
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.services.product_services import ProductService

router = APIRouter()

@router.post("/", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=201)
async def create(product: ProductCreate, _current_user: User = Depends(get_current_user)):
    created_product = await ProductService.create_product(product)
    return success_response("Product created successfully", created_product)

@router.patch("/{id}/images", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def upload_product_images(
    id: PydanticObjectId, 
    images: List[UploadFile] = File(...),
    _current_user: User = Depends(get_current_user),
):
    updated_product = await ProductService.upload_product_images(id, images)
    if not updated_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return success_response("Product images uploaded successfully", updated_product)

@router.get("/", response_model=ApiResponse[PaginatedResponse[ProductResponse]], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def list_products(query_params: ProductQueryParams = Depends()):
    products, next_cursor = await ProductQueryService.list_products(query_params)
    
    paginated_data = PaginatedResponse(
        data=products,
        meta={"has_next_page": next_cursor is not None, "next_cursor": next_cursor}
    )
    return success_response("Products fetched successfully", paginated_data)

@router.get("/{id}", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def read_one(id: PydanticObjectId):
    product = await ProductQueryService.get_product(id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return success_response("Product fetched successfully", product)


@router.patch("/{id}", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def update(id: PydanticObjectId, product: ProductUpdate, _current_user: User = Depends(get_current_user)):
    updated = await ProductService.update_product(id, product)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return success_response("Product updated successfully", updated)


@router.post("/{id}/variants", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def add_variant(id: PydanticObjectId, variant: ProductVariantCreate, _current_user: User = Depends(get_current_user)):
    updated_product = await ProductService.add_variant(id, variant)
    return success_response("Variant added successfully", updated_product)


@router.patch("/{id}/variants/{sku}", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def update_variant(
    id: PydanticObjectId,
    sku: str,
    variant: ProductVariantUpdate,
    _current_user: User = Depends(get_current_user),
):
    updated_product = await ProductService.update_variant(id, sku, variant)
    return success_response("Variant updated successfully", updated_product)


@router.delete("/{id}/variants/{sku}", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def delete_variant(id: PydanticObjectId, sku: str, _current_user: User = Depends(get_current_user)):
    updated_product = await ProductService.delete_variant(id, sku)
    return success_response("Variant deleted successfully", updated_product)


@router.delete("/{id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
async def delete(id: PydanticObjectId, _current_user: User = Depends(get_current_user)):
    success = await ProductService.delete_product(id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return success_response("Product deleted successfully")
