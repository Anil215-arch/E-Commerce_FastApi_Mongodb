from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from beanie import PydanticObjectId

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(None, max_length=1000)
    images: List[str] = Field(default_factory=list)
    
    @model_validator(mode="before")
    @classmethod
    def normalize_review(cls, data):
        if isinstance(data, dict) and "review" in data and isinstance(data["review"], str):
            data["review"] = data["review"].strip()
        return data
    
class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    review: Optional[str] = Field(None, max_length=1000)
    images: Optional[List[str]] = None
    
    @model_validator(mode="before")
    @classmethod
    def normalize_review(cls, data):
        if isinstance(data, dict) and "review" in data and isinstance(data["review"], str):
            data["review"] = data["review"].strip()
        return data

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
    