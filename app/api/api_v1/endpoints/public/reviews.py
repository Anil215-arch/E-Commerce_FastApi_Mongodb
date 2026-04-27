from fastapi import APIRouter, Request, status, Query
from beanie import PydanticObjectId
from typing import Optional

from app.core.rate_limiter import ip_key_func, limiter
from app.schemas.review_rating_schema import ReviewResponse
from app.services.review_rating_services import ReviewService
from app.schemas.common_schema import ApiResponse, PaginatedResponse, PaginationMeta
from app.utils.responses import success_response
from app.core.i18n import t
from app.core.message_keys import Msg

router = APIRouter()

@router.get("/products/{product_id}/reviews", response_model=ApiResponse[PaginatedResponse[ReviewResponse]], status_code=status.HTTP_200_OK)
@limiter.limit("60/minute", key_func=ip_key_func)
async def get_product_reviews(
    request: Request,
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
    return success_response(t(request, Msg.REVIEWS_FETCHED_SUCCESSFULLY), paginated_data)
