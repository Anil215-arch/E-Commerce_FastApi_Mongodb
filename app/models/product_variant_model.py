from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class ProductVariant(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    price: int = Field(..., gt=0)
    discount_price: Optional[int] = Field(None, gt=0)
    
    available_stock: int = Field(..., ge=0)
    reserved_stock: int = Field(default=0, ge=0)
    attributes: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def map_legacy_stock(cls, data: Any):
        """Self-heals legacy database documents and prevents data drift."""
        if isinstance(data, dict):
            if "available_stock" not in data:
                if "stock" in data:
                    data["available_stock"] = data.pop("stock")
                else:
                    data["available_stock"] = 0

            if "reserved_stock" not in data:
                data["reserved_stock"] = 0

        return data

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
