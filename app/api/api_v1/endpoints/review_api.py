from fastapi import APIRouter, Depends, Request, status, Query
from beanie import PydanticObjectId
from typing import Optional

from app.core.rate_limiter import ip_key_func, limiter, user_limiter
from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.review_rating_schema import ReviewCreate, ReviewUpdate, ReviewResponse
from app.services.review_rating_services import ReviewService
from app.schemas.common_schema import ApiResponse, PaginatedResponse, PaginationMeta
from app.utils.responses import success_response

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
    return success_response("Reviews fetched successfully", paginated_data)


@router.post("/products/{product_id}", response_model=ApiResponse[ReviewResponse], status_code=status.HTTP_201_CREATED)
@user_limiter.limit("10/minute")
async def create_product_review(request: Request, product_id: PydanticObjectId, review_in: ReviewCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    review = await ReviewService.create_review(user_id, product_id, review_in)
    return success_response("Review created successfully", review)


@router.patch("/{review_id}", response_model=ApiResponse[ReviewResponse], status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def update_existing_review(request: Request, review_id: PydanticObjectId, review_in: ReviewUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    review = await ReviewService.update_review(review_id, user_id, review_in)
    return success_response("Review updated successfully", review)


@router.delete("/{review_id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def delete_existing_review(request: Request, review_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    await ReviewService.delete_review(review_id, user_id)
    return success_response("Review deleted successfully")
