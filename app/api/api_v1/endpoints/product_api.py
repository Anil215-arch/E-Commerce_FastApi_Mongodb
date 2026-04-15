from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from beanie import PydanticObjectId
from typing import List

from app.core.user_role import UserRole
from app.services.product_query_services import ProductQueryService
from app.schemas.product_query_schema import ProductQueryParams
from app.schemas.common_schema import PaginatedResponse, PaginationMeta
from app.core.dependencies import RoleChecker, get_current_user
from app.models.user_model import User
from app.schemas.product_schema import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.product_variant_schema import ProductVariantCreate, ProductVariantUpdate
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.services.product_services import ProductService

router = APIRouter()
manage_product_access = Depends(RoleChecker([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.SELLER]))

@router.post("/", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=201)
async def create(
    product: ProductCreate,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_product_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    created_product = await ProductService.create_product(product, _current_user.id)
    return success_response("Product created successfully", created_product)

@router.patch("/{id}/images", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def upload_product_images(
    id: PydanticObjectId, 
    images: List[UploadFile] = File(...),
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_product_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    updated_product = await ProductService.upload_product_images(id, images, _current_user.id)
    if not updated_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return success_response("Product images uploaded successfully", updated_product)

@router.get("/", response_model=ApiResponse[PaginatedResponse[ProductResponse]], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def list_products(query_params: ProductQueryParams = Depends()):
    products, next_cursor, has_next_page = await ProductQueryService.list_products(query_params)
    
    paginated_data = PaginatedResponse(
        items=products,
        meta=PaginationMeta(
            has_next_page=has_next_page, 
            next_cursor=next_cursor,
        ),
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
async def update(
    id: PydanticObjectId,
    product: ProductUpdate,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_product_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    updated = await ProductService.update_product(id, product, _current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return success_response("Product updated successfully", updated)


@router.post("/{id}/variants", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def add_variant(
    id: PydanticObjectId,
    variant: ProductVariantCreate,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_product_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    updated_product = await ProductService.add_variant(id, variant, _current_user.id)
    return success_response("Variant added successfully", updated_product)


@router.patch("/{id}/variants/{sku}", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def update_variant(
    id: PydanticObjectId,
    sku: str,
    variant: ProductVariantUpdate,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_product_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    updated_product = await ProductService.update_variant(id, sku, variant, _current_user.id)
    return success_response("Variant updated successfully", updated_product)


@router.delete("/{id}/variants/{sku}", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def delete_variant(
    id: PydanticObjectId,
    sku: str,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_product_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    updated_product = await ProductService.delete_variant(id, sku, _current_user.id)
    return success_response("Variant deleted successfully", updated_product)


@router.delete("/{id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
async def delete(
    id: PydanticObjectId,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_product_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    success = await ProductService.delete_product(id, _current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or already deleted"
        )
    return success_response("Product deleted successfully")
