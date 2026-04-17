from fastapi import APIRouter, Depends, status, HTTPException
from beanie import PydanticObjectId

from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.review_rating_schema import ReviewCreate, ReviewUpdate, ReviewResponse
from app.services.review_rating_services import ReviewService
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response

router = APIRouter()


@router.post("/products/{product_id}", response_model=ApiResponse[ReviewResponse], status_code=status.HTTP_201_CREATED)
async def create_product_review(product_id: PydanticObjectId, review_in: ReviewCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    review = await ReviewService.create_review(user_id, product_id, review_in)
    return success_response("Review created successfully", review)

@router.patch("/{review_id}", response_model=ApiResponse[ReviewResponse], status_code=status.HTTP_200_OK)
async def update_existing_review(review_id: PydanticObjectId, review_in: ReviewUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    review = await ReviewService.update_review(review_id, user_id, review_in)
    return success_response("Review updated successfully", review)

@router.delete("/{review_id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
async def delete_existing_review(review_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    await ReviewService.delete_review(review_id, user_id)
    return success_response("Review deleted successfully")