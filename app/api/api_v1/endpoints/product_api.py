from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from beanie import PydanticObjectId
from typing import List
from app.core.i18n import get_language, t
from app.core.message_keys import Msg
from app.core.dependencies import get_current_user, _require_user_id, RoleChecker
from app.core.rate_limiter import ip_key_func, limiter, user_limiter
from app.core.user_role import UserRole
from app.models.user_model import User
from app.services.product_query_services import ProductQueryService
from app.schemas.product_query_schema import ProductQueryParams
from app.schemas.common_schema import PaginatedResponse, PaginationMeta, ApiResponse
from app.schemas.product_schema import ProductCreate, ProductManageResponse, ProductUpdate, ProductResponse
from app.schemas.product_variant_schema import ProductVariantCreate, ProductVariantUpdate
from app.services.product_services import ProductService
from app.utils.responses import success_response

router = APIRouter()
seller_dependency = Depends(RoleChecker([UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN]))


@router.get("", response_model=ApiResponse[PaginatedResponse[ProductResponse]], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@limiter.limit("60/minute", key_func=ip_key_func)
async def list_all_products(request: Request, query_params: ProductQueryParams = Depends()):
    """
    Public endpoint to fetch a paginated list of available products.
    """
    language = get_language(request)
    products, next_cursor, has_next_page = await ProductQueryService.list_products(query_params, language=language)

    paginated_data = PaginatedResponse(
        items=products,
        meta=PaginationMeta(
            has_next_page=has_next_page,
            next_cursor=next_cursor,
        ),
    )
    return success_response(t(request, Msg.PRODUCTS_FETCHED_SUCCESSFULLY, language=language), paginated_data)


@router.get("/{id}", response_model=ApiResponse[ProductResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@limiter.limit("60/minute", key_func=ip_key_func)
async def read_one(request: Request, id: PydanticObjectId):
    """
    Public endpoint to fetch the specific details of a single product.
    """
    product = await ProductQueryService.get_product(id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t(request, Msg.PRODUCT_NOT_FOUND),
        )
    return success_response(t(request, Msg.PRODUCT_FETCHED_SUCCESSFULLY), product)


@router.post("", response_model=ApiResponse[ProductManageResponse], status_code=status.HTTP_201_CREATED, dependencies=[seller_dependency])
@user_limiter.limit("5/minute")
async def create_product(request: Request, product: ProductCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    created_product = await ProductService.create_product(product, user_id)
    return success_response(t(request, Msg.PRODUCT_CREATED_SUCCESSFULLY), created_product)

@router.patch("/{id}/images", response_model=ApiResponse[ProductManageResponse], dependencies=[seller_dependency])
@user_limiter.limit("10/minute")
async def upload_images(request: Request, id: PydanticObjectId, images: List[UploadFile] = File(...), current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated = await ProductService.upload_product_images(id, images, user_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.PRODUCT_NOT_FOUND))
    return success_response(t(request, Msg.IMAGES_UPLOADED_SUCCESSFULLY), updated)

@router.patch("/{id}", response_model=ApiResponse[ProductManageResponse], dependencies=[seller_dependency])
@user_limiter.limit("10/minute")
async def update_product(request: Request, id: PydanticObjectId, product: ProductUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated = await ProductService.update_product(id, product, user_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.PRODUCT_NOT_FOUND))
    return success_response(t(request, Msg.PRODUCT_UPDATED_SUCCESSFULLY), updated)


@router.post("/{id}/variants", response_model=ApiResponse[ProductManageResponse], dependencies=[seller_dependency])
@user_limiter.limit("10/minute")
async def add_variant(request: Request, id: PydanticObjectId, variant: ProductVariantCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated_product = await ProductService.add_variant(id, variant, user_id)
    return success_response(t(request, Msg.VARIANT_ADDED_SUCCESSFULLY), updated_product)

@router.patch("/{id}/variants/{sku}", response_model=ApiResponse[ProductManageResponse], dependencies=[seller_dependency])
@user_limiter.limit("10/minute")
async def update_variant(request: Request, id: PydanticObjectId, sku: str, variant: ProductVariantUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated_product = await ProductService.update_variant(id, sku, variant, user_id)
    return success_response(t(request, Msg.VARIANT_UPDATED_SUCCESSFULLY), updated_product)

@router.delete("/{id}/variants/{sku}", response_model=ApiResponse[ProductManageResponse], dependencies=[seller_dependency])
@user_limiter.limit("10/minute")
async def delete_variant(request: Request, id: PydanticObjectId, sku: str, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated_product = await ProductService.delete_variant(id, sku, user_id)
    return success_response(t(request, Msg.VARIANT_DELETED_SUCCESSFULLY), updated_product)


@router.delete("/{id}", response_model=ApiResponse[None], dependencies=[seller_dependency])
@user_limiter.limit("10/minute")
async def delete_product(
    request: Request,
    id: PydanticObjectId,
    current_user: User = Depends(get_current_user),
):
    if not await ProductService.delete_product(id, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.PRODUCT_NOT_FOUND))
    return success_response(t(request, Msg.PRODUCT_DELETED_SUCCESSFULLY))
