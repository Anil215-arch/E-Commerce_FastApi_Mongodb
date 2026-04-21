from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator, ConfigDict


class ProductVariantCreate(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    price: int = Field(..., gt=0)
    discount_price: Optional[int] = Field(None, gt=0)
    
    available_stock: int = Field(..., ge=0)
    reserved_stock: int = Field(0, ge=0)
    attributes: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_discount_price(self):
        if self.discount_price is not None and self.discount_price >= self.price:
            raise ValueError("discount_price must be less than price")
        return self
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sku": "APPLE-MBA-M2-256",
                "price": 99999,
                "discount_price": 19999,
                "available_stock": 10,
                "reserved_stock": 0,
                "attributes": {
                    "Processor": "Apple M2",
                    "RAM": "8GB",
                    "Storage": "256GB SSD"
                }
            }
        }
    )



class ProductVariantUpdate(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    price: Optional[int] = Field(None, gt=0)
    discount_price: Optional[int] = Field(None, gt=0)
    available_stock: Optional[int] = Field(None, ge=0)
    reserved_stock: Optional[int] = Field(None, ge=0)
    attributes: Optional[Dict[str, str]] = None

    @model_validator(mode="after")
    def validate_discount_price(self):
        if self.discount_price is not None and self.price is not None and self.discount_price >= self.price:
            raise ValueError("discount_price must be less than price")
        return self

class ProductVariantResponse(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    price: int = Field(..., gt=0)
    discount_price: Optional[int] = Field(None, gt=0)
    
    available_stock: int = Field(..., ge=0)
    reserved_stock: int = Field(..., ge=0)
    attributes: Dict[str, str] = Field(default_factory=dict)
