from typing import Optional
from app.models.product_model import Product
from app.models.category_model import Category
from app.schemas.product_schema import ProductResponse, ProductManageResponse
from app.schemas.category_schema import CategorySummaryResponse
from app.schemas.product_variant_schema import ProductVariantResponse

class ProductMapper:
    """
    Dedicated mapping layer to serialize database models into API schemas.
    Completely decouples read/write services from response formatting.
    """
    
    @staticmethod
    def _localized_category_name(category: Optional[Category], language: Optional[str]) -> str:
        if category and category.id is not None:
            if language and language in category.translations:
                translated_name = category.translations[language].name
                if translated_name:
                    return translated_name
            return category.name
        return "Unknown Category"

    @staticmethod
    def _localized_product_content(product: Product, language: Optional[str]) -> tuple[str, str]:
        if language and language in product.translations:
            translated = product.translations[language]
            return translated.name, translated.description
        return product.name, product.description

    @staticmethod
    def serialize_product(
        product: Product,
        category: Optional[Category],
        language: Optional[str] = None,
        include_translations: bool = False,
    ) -> ProductResponse | ProductManageResponse:
        if product.id is None:
            raise ValueError("Product ID is missing. Persist product before serialization.")

        category_name = ProductMapper._localized_category_name(category, language)
        if category and category.id is not None:
            category_summary = CategorySummaryResponse(_id=category.id, name=category_name)
        else:
            category_summary = CategorySummaryResponse(_id=product.category_id, name=category_name)

        localized_name, localized_description = ProductMapper._localized_product_content(product, language)

        variants = [ProductVariantResponse(**variant.model_dump()) for variant in product.variants]

        base_payload = dict(
            _id=product.id,
            name=localized_name,
            description=localized_description,
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

        if include_translations:
            return ProductManageResponse(
                **base_payload,
                translations={
                    lang: {
                        "name": translated.name,
                        "description": translated.description,
                    }
                    for lang, translated in product.translations.items()
                },
            )

        return ProductResponse(**base_payload)