from typing import Optional
from app.models.product_model import Product
from app.models.category_model import Category
from app.schemas.product_schema import ProductResponse
from app.schemas.category_schema import CategorySummaryResponse
from app.schemas.product_variant_schema import ProductVariantResponse

class ProductMapper:
    """
    Dedicated mapping layer to serialize database models into API schemas.
    Completely decouples read/write services from response formatting.
    """
    
    @staticmethod
    def serialize_product(product: Product, category: Optional[Category]) -> ProductResponse:
        if product.id is None:
            raise ValueError("Product ID is missing. Persist product before serialization.")
        
        if category and category.id is not None:
            category_summary = CategorySummaryResponse(_id=category.id, name=category.name)
        else:
            category_summary = CategorySummaryResponse(_id=product.category_id, name="Unknown Category")

        variants = [ProductVariantResponse(**variant.model_dump()) for variant in product.variants]

        return ProductResponse(
            _id=product.id,
            name=product.name,
            description=product.description,
            brand=product.brand,
            category=category_summary,
            variants=variants,
            price=product.price,
            images=product.images,
            average_rating=product.average_rating,
            num_reviews=product.num_reviews,
            rating_sum=product.rating_sum,
            rating_breakdown=product.rating_breakdown,
            specifications=product.specifications,
            is_available=product.is_available,
            is_featured=product.is_featured,
        )