from typing import List, Dict, Any
from beanie import Insert, PydanticObjectId, Replace, Save, SaveChanges, before_event
from pydantic import Field, model_validator
from pymongo import TEXT, IndexModel, ASCENDING
from app.models.product_variant_model import ProductVariant
from app.models.base_model import AuditDocument

class Product(AuditDocument):
    name: str = Field(..., min_length=3, max_length=200, pattern=r"^[^<>]+$")
    description: str = Field(..., min_length=10, max_length=5000, pattern=r"^[^<>]+$")
    brand: str = Field(..., min_length=2, max_length=100, pattern=r"^[^<>]+$")
    category_id: PydanticObjectId

    variants: List[ProductVariant] = Field(default_factory=list, max_length=100)
    price: int = Field(default=0, ge=0)

    images: List[str] = Field(default_factory=list, max_length=20)

    num_reviews: int = Field(default=0, ge=0)
    rating_sum: int = Field(default=0, ge=0, le=10_000_000)
    average_rating: float = Field(default=0.0, ge=0, le=5)
    
    rating_breakdown: Dict[str, int] = Field(
        default_factory=lambda: {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    )
    specifications: Dict[str, str] = Field(default_factory=dict)

    is_available: bool = True
    is_featured: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any):
        if isinstance(data, dict):
            if "name" in data and isinstance(data["name"], str):
                data["name"] = data["name"].strip()
            if "description" in data and isinstance(data["description"], str):
                data["description"] = data["description"].strip()
            if "brand" in data and isinstance(data["brand"], str):
                data["brand"] = data["brand"].strip().title()
        return data

    @model_validator(mode="after")
    def enforce_rules(self):
        # 1. Variants required
        if not self.variants:
            raise ValueError("Product must have at least one variant")

        # 2. SKU uniqueness
        skus = [v.sku for v in self.variants]
        if len(skus) != len(set(skus)):
            raise ValueError("Duplicate SKUs are not allowed")

        # 3. Image validation (minimal, no type change)
        seen_images = set()
        for img in self.images:
            img_str = str(img).strip()

            if not img_str:
                raise ValueError("Empty image URL not allowed")

            if len(img_str) > 500:
                raise ValueError("Image URL too long")

            if img_str in seen_images:
                raise ValueError("Duplicate image URLs")

            seen_images.add(img_str)

        # 4. Specification validation (minimal, no type change)
        for k, v in self.specifications.items():
            key = str(k).strip()
            if not key:
                raise ValueError("Specification keys cannot be empty")
            if len(key) > 50 or len(str(v)) > 500:
                raise ValueError("Specification size exceeded")

        # 5. Rating validation
        expected_keys = {"1", "2", "3", "4", "5"}
        if set(self.rating_breakdown.keys()) != expected_keys:
            raise ValueError("Invalid rating breakdown keys")

        for val in self.rating_breakdown.values():
            if not isinstance(val, int) or val < 0:
                raise ValueError("Invalid rating values")

        total_reviews = sum(self.rating_breakdown.values())
        if total_reviews != self.num_reviews:
            raise ValueError("rating_breakdown mismatch")

        calculated_sum = sum(int(k) * v for k, v in self.rating_breakdown.items())
        if calculated_sum != self.rating_sum:
            raise ValueError("rating_sum mismatch")

        if self.num_reviews == 0:
            if self.average_rating != 0:
                raise ValueError("average_rating must be 0 when no reviews")
        else:
            expected_avg = self.rating_sum / self.num_reviews
            if abs(self.average_rating - expected_avg) > 0.01:
                raise ValueError("average_rating mismatch")

        # 6. Price sync (safe)
        self.price = min(
            (v.effective_price for v in self.variants if v.effective_price > 0),
            default=0
        )

        return self

    @before_event([Insert, Replace, Save, SaveChanges])
    def sync_price_db(self) -> None:
        self.price = min(
            (variant.effective_price for variant in self.variants if variant.effective_price > 0),
            default=0
        )

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