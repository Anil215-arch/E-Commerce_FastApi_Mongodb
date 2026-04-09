from typing import Optional, List, Dict
from beanie import Document, Insert, PydanticObjectId, Replace, Save, SaveChanges, before_event
from pydantic import Field
from pymongo import IndexModel, ASCENDING
from app.models.product_variant_model import ProductVariant


class Product(Document):
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)

    brand: str = Field(..., min_length=2, max_length=100)
    category_id: PydanticObjectId

    variants: List[ProductVariant] = Field(default_factory=list)
    price: int = Field(default=0, ge=0)

    images: List[str] = Field(default_factory=list)

    rating: float = Field(default=0.0, ge=0, le=5)
    num_reviews: int = Field(default=0, ge=0)

    specifications: Dict[str, str] = Field(default_factory=dict)

    is_available: bool = True
    is_featured: bool = False

    @before_event([Insert, Replace, Save, SaveChanges])
    def sync_price(self) -> None:
        self.price = min((variant.price for variant in self.variants), default=0)

    class Settings:
        name = "products"
        indexes = [
            IndexModel([("category_id", ASCENDING)]),
            IndexModel([("variants.sku", ASCENDING)], unique=True),
            IndexModel([("price", ASCENDING), ("_id", ASCENDING)]),
            IndexModel([("rating", ASCENDING), ("_id", ASCENDING)]),
        ]
