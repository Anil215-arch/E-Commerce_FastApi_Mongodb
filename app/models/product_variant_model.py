from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator


class ProductVariant(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    price: int = Field(..., gt=0)
    discount_price: Optional[int] = Field(None, gt=0)
    stock: int = Field(..., ge=0)
    attributes: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_discount_price(self):
        if self.discount_price is not None and self.discount_price >= self.price:
            raise ValueError("discount_price must be less than price")
        return self

    @property
    def effective_price(self) -> int:
        """
        Returns the discount_price if it exists; otherwise returns the base price.
        """
        if self.discount_price and self.discount_price > 0:
            return self.discount_price
        return self.price