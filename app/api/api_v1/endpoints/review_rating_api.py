from fastapi import APIRouter, Depends, status, HTTPException, Query
from beanie import PydanticObjectId
from typing import Optional

from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.review_rating_schema import ReviewCreate, ReviewUpdate, ReviewResponse
from app.services.review_rating_services import ReviewService
from app.schemas.common_schema import ApiResponse, PaginatedResponse, PaginationMeta
from app.utils.responses import success_response

router = APIRouter()

@router.post("/products/{product_id}/reviews", response_model=ApiResponse[ReviewResponse], status_code=status.HTTP_201_CREATED)
async def create_product_review(
    product_id: PydanticObjectId,
    review_in: ReviewCreate,
    current_user: User = Depends(get_current_user)
):
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    review = await ReviewService.create_review(current_user.id, product_id, review_in)
    return success_response("Review created successfully", review)

@router.patch("/reviews/{review_id}", response_model=ApiResponse[ReviewResponse], status_code=status.HTTP_200_OK)
async def update_existing_review(
    review_id: PydanticObjectId,
    review_in: ReviewUpdate,
    current_user: User = Depends(get_current_user)
):
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required") 
    
    review = await ReviewService.update_review(review_id, current_user.id, review_in)
    return success_response("Review updated successfully", review)

@router.delete("/reviews/{review_id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
async def delete_existing_review(
    review_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    await ReviewService.delete_review(review_id, current_user.id)
    return success_response("Review deleted successfully")

@router.get("/products/{product_id}/reviews", response_model=ApiResponse[PaginatedResponse[ReviewResponse]], status_code=status.HTTP_200_OK)
async def get_product_reviews(
    product_id: PydanticObjectId,
    limit: int = Query(10, ge=1, le=50),
    cursor: Optional[str] = Query(None)
):
    reviews, next_cursor, has_next_page = await ReviewService.list_product_reviews(product_id, limit, cursor)
    
    paginated_data = PaginatedResponse(
        items=reviews,
        meta=PaginationMeta(
            has_next_page=has_next_page, 
            next_cursor=next_cursor,
        ),
    )
    return success_response("Reviews fetched successfully", paginated_data)