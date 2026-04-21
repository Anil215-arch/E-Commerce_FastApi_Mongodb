from pydantic import BaseModel, Field, ConfigDict, field_serializer, model_validator
from typing import Optional, List, Dict
from beanie import PydanticObjectId
from app.schemas.category_schema import CategorySummaryResponse
from app.schemas.product_variant_schema import ProductVariantCreate, ProductVariantUpdate, ProductVariantResponse

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)

    brand: str = Field(..., min_length=2, max_length=100)
    category_id: PydanticObjectId

    variants: List[ProductVariantCreate] = Field(default_factory=list)

    specifications: Dict[str, str] = Field(default_factory=dict)

    is_available: bool = True
    is_featured: bool = False

    @model_validator(mode="after")
    def validate_variants_size(self):
        if len(self.variants) == 0:
            raise ValueError("At least one product variant is required.")
        return self

    @model_validator(mode="after")
    def validate_unique_variant_sku(self):
        sku_counts = [variant.sku for variant in self.variants]
        if len(sku_counts) != len(set(sku_counts)):
            raise ValueError("Variant SKUs must be unique within a product.")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "MacBook Air M2",
                "description": "Thin and lightweight Apple laptop with M2 chip",
                "brand": "Apple",
                "category_id": "507f1f77bcf86cd799439011",
                "variants": [
                    {
                        "sku": "APPLE-MBA-M2-256",
                        "price": 99999,
                        "discount_price": 19999,
                        "available_stock": 10,
                        "reserved_stock": 0,
                        "attributes": {}
                    }
                ],
                "rating": 4.5,
                "num_reviews": 120,
                "specifications": {
                    "Processor": "Apple M2",
                    "RAM": "8GB",
                    "Storage": "256GB SSD"
                },
                "is_available": True,
                "is_featured": True
            }
        }
    )


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, min_length=10)

    brand: Optional[str] = Field(None, min_length=2, max_length=100)
    category_id: Optional[PydanticObjectId] = None

    variants: Optional[List[ProductVariantUpdate]] = None

    images: Optional[List[str]] = None

    specifications: Optional[Dict[str, str]] = None

    is_available: Optional[bool] = None
    is_featured: Optional[bool] = None

    @model_validator(mode="after")
    def validate_unique_variant_sku(self):
        if self.variants is None:
            return self

        sku_counts = [variant.sku for variant in self.variants]
        if len(sku_counts) != len(set(sku_counts)):
            raise ValueError("Variant SKUs must be unique within a product.")
        return self


class ProductResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    name: str
    description: str

    brand: str
    category: CategorySummaryResponse

    variants: List[ProductVariantResponse]
    price: int

    images: List[str]

    average_rating: float
    num_reviews: int
    rating_sum: int
    rating_breakdown: Dict[str, int]


    specifications: Dict[str, str]

    is_available: bool
    is_featured: bool

    @field_serializer("id")
    def serialize_id(self, value):
        return str(value)

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
