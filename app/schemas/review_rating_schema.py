from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from beanie import PydanticObjectId

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(None, max_length=1000)
    images: List[str] = Field(default_factory=list)
    
class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    review: Optional[str] = Field(None, max_length=1000)
    images: Optional[List[str]] = None

class ReviewResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    product_id: PydanticObjectId
    user_id: PydanticObjectId
    rating: int
    review: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
    