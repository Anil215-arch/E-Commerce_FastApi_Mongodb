from pydantic import BaseModel, Field, ConfigDict, field_serializer, model_validator
from typing import Optional, List, Dict
from beanie import PydanticObjectId
from app.core.i18n import CONTENT_TRANSLATION_LANGUAGES
from app.schemas.category_schema import CategorySummaryResponse
from app.schemas.product_variant_schema import ProductVariantCreate, ProductVariantUpdate, ProductVariantResponse


class ProductTranslationSchema(BaseModel):
    name: str = Field(..., min_length=3, max_length=200, pattern=r"^[^<>]+$")
    description: str = Field(..., min_length=10, max_length=5000, pattern=r"^[^<>]+$")

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, data):
        if isinstance(data, dict):
            if "name" in data and isinstance(data["name"], str):
                data["name"] = data["name"].strip()
            if "description" in data and isinstance(data["description"], str):
                data["description"] = data["description"].strip()
        return data

    model_config = ConfigDict(from_attributes=True)

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)

    brand: str = Field(..., min_length=2, max_length=100)
    category_id: PydanticObjectId

    variants: List[ProductVariantCreate] = Field(default_factory=list) 

    specifications: Dict[str, str] = Field(default_factory=dict)
    translations: Optional[Dict[str, ProductTranslationSchema]] = None

    is_available: bool = True
    is_featured: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, data):
        if isinstance(data, dict):
            if "name" in data:
                data["name"] = data["name"].strip()
            if "description" in data:
                data["description"] = data["description"].strip()
            if "brand" in data:
                data["brand"] = data["brand"].strip()
        return data

    @model_validator(mode="after")
    def validate_variants(self):
        if len(self.variants) == 0:
            raise ValueError("At least one product variant is required.")

        skus = [variant.sku for variant in self.variants]
        if len(skus) != len(set(skus)):
            raise ValueError("Variant SKUs must be unique within a product.")

        if self.translations is not None:
            invalid_langs = [lang for lang in self.translations.keys() if lang not in CONTENT_TRANSLATION_LANGUAGES]
            if invalid_langs:
                raise ValueError("Invalid translation language key.")

        return self

    @model_validator(mode="after")
    def validate_translations(self):
        if self.translations is not None:
            invalid_langs = [
                lang for lang in self.translations.keys()
                if lang not in CONTENT_TRANSLATION_LANGUAGES
            ]
            if invalid_langs:
                raise ValueError("Invalid translation language key.")
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
    translations: Optional[Dict[str, ProductTranslationSchema]] = None

    is_available: Optional[bool] = None
    is_featured: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, data):
        if isinstance(data, dict):
            if "name" in data:
                data["name"] = data["name"].strip()
            if "description" in data:
                data["description"] = data["description"].strip()
            if "brand" in data:
                data["brand"] = data["brand"].strip()
        return data

    @model_validator(mode="after")
    def validate_unique_variant_sku(self):
        if self.variants is None:
            return self

        skus = [variant.sku for variant in self.variants]
        if len(skus) != len(set(skus)):
            raise ValueError("Variant SKUs must be unique within a product.")

        if self.translations is not None:
            invalid_langs = [lang for lang in self.translations.keys() if lang not in CONTENT_TRANSLATION_LANGUAGES]
            if invalid_langs:
                raise ValueError("Invalid translation language key.")

        return self

    @model_validator(mode="after")
    def validate_translations(self):
        if self.translations is not None:
            invalid_langs = [
                lang for lang in self.translations.keys()
                if lang not in CONTENT_TRANSLATION_LANGUAGES
            ]
            if invalid_langs:
                raise ValueError("Invalid translation language key.")
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


class ProductManageResponse(ProductResponse):
    translations: Dict[str, ProductTranslationSchema] = Field(default_factory=dict)
