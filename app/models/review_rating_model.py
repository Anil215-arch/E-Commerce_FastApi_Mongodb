from typing import Optional, List
from beanie import PydanticObjectId
from pydantic import Field
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
        
    