from fastapi import APIRouter, status, Query
from beanie import PydanticObjectId
from typing import Optional

from app.schemas.review_rating_schema import ReviewResponse
from app.services.review_rating_services import ReviewService
from app.schemas.common_schema import ApiResponse, PaginatedResponse, PaginationMeta
from app.utils.responses import success_response

router = APIRouter()

@router.get("/products/{product_id}/reviews", response_model=ApiResponse[PaginatedResponse[ReviewResponse]], status_code=status.HTTP_200_OK)
async def get_product_reviews(
    product_id: PydanticObjectId,
    limit: int = Query(10, ge=1, le=50),
    cursor: Optional[str] = Query(None)
):
    """
    Public endpoint to read reviews for a specific product.
    """
    reviews, next_cursor, has_next_page = await ReviewService.list_product_reviews(product_id, limit, cursor)
    
    paginated_data = PaginatedResponse(
        items=reviews,
        meta=PaginationMeta(
            has_next_page=has_next_page, 
            next_cursor=next_cursor,
        ),
    )
    return success_response("Reviews fetched successfully", paginated_data)