from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from beanie import PydanticObjectId

class SortField(str, Enum):
    PRICE = "price"
    RATING = "rating"
    CREATED_AT = "created_at"

class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"

class ProductQueryParams(BaseModel):
    cursor: Optional[str] = Field(default=None, description="URL-safe Base64 encoded cursor")
    limit: int = Field(default=10, ge=1, le=50, description="Max 50 items per request to prevent OOM crashes")

    sort_by: SortField = Field(default=SortField.CREATED_AT)
    sort_order: SortOrder = Field(default=SortOrder.DESC)

    category_id: Optional[PydanticObjectId] = None
    brand: Optional[str] = Field(default=None, min_length=2, max_length=100)
    
    min_price: Optional[int] = Field(default=None, ge=0)
    max_price: Optional[int] = Field(default=None, ge=0)

    @field_validator("brand", mode="before")
    @classmethod
    def normalize_brand(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and isinstance(v, str):
            return v.strip().title()
        return v

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot be greater than max_price")
        return self

    model_config = ConfigDict(extra="forbid")