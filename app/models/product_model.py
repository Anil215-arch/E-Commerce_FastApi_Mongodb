from typing import Optional, List, Dict
from beanie import Document, Insert, PydanticObjectId, Replace, Save, SaveChanges, before_event
from pydantic import Field
from pymongo import TEXT, IndexModel, ASCENDING
from app.models.product_variant_model import ProductVariant
from app.models.base_model import AuditDocument

class Product(AuditDocument):
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)

    brand: str = Field(..., min_length=2, max_length=100)
    category_id: PydanticObjectId

    variants: List[ProductVariant] = Field(default_factory=list)
    price: int = Field(default=0, ge=0)

    images: List[str] = Field(default_factory=list)

    num_reviews: int = Field(default=0, ge=0)
    rating_sum: int = Field(default=0, ge=0)
    average_rating: float = Field(default=0.0, ge=0, le=5)
    
    rating_breakdown: Dict[str, int] = Field(
        default_factory=lambda: {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    )
    specifications: Dict[str, str] = Field(default_factory=dict)

    is_available: bool = True
    is_featured: bool = False
    
    @before_event([Insert, Replace, Save, SaveChanges])
    def sync_price(self) -> None:
        self.price = min((variant.effective_price for variant in self.variants), default=0)

    class Settings:
        name = "products"
        indexes = [
            IndexModel([("category_id", ASCENDING)]),
            IndexModel([("variants.sku", ASCENDING)], unique=True),
            IndexModel([("price", ASCENDING), ("_id", ASCENDING)]),
            IndexModel([("average_rating", ASCENDING), ("_id", ASCENDING)]),
            IndexModel(
                [("name", TEXT), ("brand", TEXT), ("description", TEXT)],
                weights={"name": 10, "brand": 5, "description": 1},
                name="product_text_search"
            )
        ]