from fastapi import APIRouter, Depends, HTTPException, Request, status
from beanie import PydanticObjectId

from app.core.rate_limiter import ip_key_func, limiter
from app.services.product_query_services import ProductQueryService
from app.schemas.product_query_schema import ProductQueryParams
from app.schemas.common_schema import PaginatedResponse, PaginationMeta, ApiResponse
from app.schemas.product_schema import ProductResponse
from app.utils.responses import success_response

router = APIRouter()

@router.get("/", response_model=ApiResponse[PaginatedResponse[ProductResponse]], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@limiter.limit("60/minute", key_func=ip_key_func)
async def list_products(request: Request, query_params: ProductQueryParams = Depends()):
    """
    Public endpoint to fetch a paginated list of available products.
    """
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
@limiter.limit("60/minute", key_func=ip_key_func)
async def read_one(request: Request, id: PydanticObjectId):
    """
    Public endpoint to fetch the specific details of a single product.
    """
    product = await ProductQueryService.get_product(id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return success_response("Product fetched successfully", product)
