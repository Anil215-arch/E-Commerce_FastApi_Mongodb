from beanie import PydanticObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError
from app.models.wishlist_model import Wishlist
from app.models.product_model import Product
from app.schemas.wishlist_schema import WishlistPopulatedResponse
from app.validators.wishlist_validator import WishlistDomainValidator
from app.core.exceptions import DomainValidationError

class WishlistService:

    @staticmethod
    async def remove_ghost_product_references(product_id: PydanticObjectId, sku: str | None = None) -> None:
        """Removes wishlist rows referencing a deleted/unavailable product or variant."""
        query: dict = {
            "product_id": product_id,
            "is_deleted": {"$ne": True},
        }
        if sku is not None:
            query["sku"] = sku

        await Wishlist.find(query).delete()
    
    @staticmethod
    async def add_item(user_id: PydanticObjectId, product_id: PydanticObjectId, sku: str) -> None:
        current_count = await Wishlist.find({"user_id": user_id, "is_deleted": {"$ne": True}}).count()
        WishlistDomainValidator.validate_capacity(current_count)
        WishlistDomainValidator.validate_sku(sku)
        # 1. Validate Product and Variant Existence
        product = await Product.find_one({"_id": product_id, "is_deleted": {"$ne": True}, "is_available": True})
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or unavailable.")

        variant = next((v for v in product.variants if v.sku == sku), None)
        if not variant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant SKU not found.")

        # 2. Atomic Insert with Index Protection
        wishlist_item = Wishlist(
            user_id=user_id,
            product_id=product_id,
            sku=sku,
            created_by=user_id,
            updated_by=user_id
        )
        
        try:
            await wishlist_item.insert()
        except DuplicateKeyError:
            # Idempotent response: If it's already there, just return success
            return

    @staticmethod
    async def remove_item(user_id: PydanticObjectId, product_id: PydanticObjectId, sku: str) -> None:
        WishlistDomainValidator.validate_sku(sku)
        result = await Wishlist.find_one(
            {"user_id": user_id, "product_id": product_id, "sku": sku, "is_deleted": {"$ne": True}}
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in wishlist.")
            
        await result.delete()

    @staticmethod
    async def get_user_wishlist(user_id: PydanticObjectId) -> list[WishlistPopulatedResponse]:
        # Fetch active wishlist entries
        wishlist_items = await Wishlist.find({"user_id": user_id, "is_deleted": {"$ne": True}}).to_list()
        if not wishlist_items:
            return []

        # Extract IDs and fetch corresponding products
        product_ids = [item.product_id for item in wishlist_items]
        products = await Product.find(
            {"_id": {"$in": product_ids}, "is_deleted": {"$ne": True}, "is_available": True}
        ).to_list()

        product_map = {product.id: product for product in products}
        populated_list: list[WishlistPopulatedResponse] = []

        # Memory mapping (Aggregation is better, but this avoids heavy NoSQL joins for now)
        for item in wishlist_items:
            product = product_map.get(item.product_id)
            # SATISFIES PYLANCE BY ENSURING IDs ARE NOT NONE
            if product and item.id is not None and product.id is not None:
                variant = next((v for v in product.variants if v.sku == item.sku), None)
                if variant:
                    populated_list.append(
                        WishlistPopulatedResponse(
                            _id=item.id,
                            product_id=product.id,
                            name=product.name,
                            brand=product.brand,
                            sku=item.sku,
                            price=variant.price, # Assumes standard pricing field exists
                            image=product.images[0] if product.images else None
                        )
                    )
        
        # Note: Ghost product cleanup is deferred to a background async worker, not the read path.
        return populated_list