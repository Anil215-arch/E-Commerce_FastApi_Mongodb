from typing import Optional, List
from beanie import PydanticObjectId
from pydantic import Field, model_validator
from pymongo import IndexModel, ASCENDING, DESCENDING
from app.models.base_model import AuditDocument

class ReviewAndRating(AuditDocument):
    product_id: PydanticObjectId
    user_id: PydanticObjectId
    
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(None, max_length=1000)
    
    # Critical for credibility
    is_verified: bool = Field(default=False) 
    images: List[str] = Field(default_factory=list)
    
    order_id: Optional[PydanticObjectId] = None  # Link to order for verification
    
    @model_validator(mode="after")
    def validate_review_integrity(self):
        if self.review is not None:
            clean_review = self.review.strip()
            if not clean_review:
                raise ValueError("Review text cannot be empty or whitespace only")
            self.review = clean_review

        if len(self.images) > 5:
            raise ValueError("You cannot attach more than 5 images")

        seen_images = set()
        for image in self.images:
            image_str = str(image).strip()
            if not image_str:
                raise ValueError("Image value cannot be empty")
            if len(image_str) > 500:
                raise ValueError("Image value is too long")
            if image_str in seen_images:
                raise ValueError("Duplicate images are not allowed")
            seen_images.add(image_str)

        return self

    class Settings:
        name = "reviews"
        indexes = [
            # Safer Partial Index
            IndexModel(
                [("product_id", ASCENDING), ("user_id", ASCENDING)], 
                unique=True,
                partialFilterExpression={"is_deleted": False},
                name="unique_active_review_v2"
            ),
            # Pagination Index
            IndexModel(
                [("product_id", ASCENDING), ("created_at", DESCENDING)],
                name="product_review_listing"
            )
        ]
        
    