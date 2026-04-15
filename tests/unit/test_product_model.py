from beanie import PydanticObjectId

from app.models.product_model import Product
from app.models.product_variant_model import ProductVariant


def test_product_sync_price_uses_effective_variant_price():
    product = Product.model_construct(
        name="Gaming Laptop",
        description="High-performance gaming laptop with dedicated GPU",
        brand="Acer",
        category_id=PydanticObjectId("507f1f77bcf86cd799439011"),
        variants=[
            ProductVariant(
                sku="ACER-16-512",
                price=120000,
                discount_price=100000,
                stock=5,
            ),
            ProductVariant(
                sku="ACER-32-1024",
                price=150000,
                discount_price=None,
                stock=3,
            ),
        ],
    )

    product.sync_price()

    assert product.price == 100000
