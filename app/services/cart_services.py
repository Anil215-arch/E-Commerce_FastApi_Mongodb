import asyncio
from datetime import datetime
from typing import Optional, List
from beanie import PydanticObjectId

from app.models.cart_model import Cart, CartItem
from app.models.product_model import Product
from app.schemas.cart_schema import CartItemAdd, CartItemUpdate, CartResponse, CartItemDetailed
from app.schemas.product_variant_schema import ProductVariantResponse

# Domain Exceptions
class CartError(Exception): pass
class CartConflictError(CartError): pass
class CartLimitExceeded(CartError): pass
class ProductUnavailable(CartError): pass
class VariantNotFound(CartError): pass
class StockExceeded(CartError): pass

class CartService:
    MAX_CART_ITEMS = 20
    MAX_RETRIES = 5

    @staticmethod
    async def get_or_create_cart(user_id: PydanticObjectId) -> Cart:
        collection = Cart.get_pymongo_collection() # type: ignore
        await collection.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {
                "user_id": user_id,
                "items": [],
                "version": 1,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )
        cart = await Cart.find_one(Cart.user_id == user_id)
        if not cart:
            raise CartError("Failed to initialize cart.")
        return cart

    @staticmethod
    async def add_to_cart(user_id: PydanticObjectId, data: CartItemAdd) -> Cart:
        for attempt in range(CartService.MAX_RETRIES):
            cart = await CartService.get_or_create_cart(user_id)
            
            product = await Product.get(data.product_id)
            if not product or getattr(product, "is_deleted", False) or not getattr(product, "is_available", True):
                raise ProductUnavailable("Product is currently unavailable or deleted.")
            
            variant = next((v for v in product.variants if v.sku == data.sku), None)
            if not variant:
                raise VariantNotFound("Variant no longer exists.")

            existing_item = next((i for i in cart.items if i.product_id == data.product_id and i.sku == data.sku), None)

            if not existing_item and len(cart.items) >= CartService.MAX_CART_ITEMS:
                raise CartLimitExceeded(f"Cart limit reached (max {CartService.MAX_CART_ITEMS} items).")

            new_items = [i.model_copy() for i in cart.items]
            
            if existing_item:
                for item in new_items:
                    if item.product_id == data.product_id and item.sku == data.sku:
                        new_qty = item.quantity + data.quantity
                        if new_qty > variant.stock:
                            raise StockExceeded(f"Insufficient stock. Available: {variant.stock}")
                        item.quantity = new_qty
                        break
            else:
                if data.quantity > variant.stock:
                    raise StockExceeded(f"Insufficient stock. Available: {variant.stock}")
                new_items.append(CartItem(**data.model_dump()))

            # FIX: Using raw Motor for flawless atomic locking and bypassing Pylance UpdateQuery errors
            collection = Cart.get_pymongo_collection() # type: ignore
            update_result = await collection.update_one(
                {"_id": cart.id, "version": cart.version},
                {
                    "$set": {"items": [i.model_dump() for i in new_items], "updated_at": datetime.utcnow()},
                    "$inc": {"version": 1}
                }
            )

            if update_result.modified_count > 0:
                updated_cart = await Cart.get(cart.id)
                if updated_cart:
                    return updated_cart
                
            await asyncio.sleep(0.01 * (attempt + 1))

        raise CartConflictError("Cart was modified concurrently. Please retry.")

    @staticmethod
    async def update_item_quantity(user_id: PydanticObjectId, product_id: PydanticObjectId, sku: str, data: CartItemUpdate) -> Cart:
        for attempt in range(CartService.MAX_RETRIES):
            cart = await Cart.find_one(Cart.user_id == user_id)
            if not cart:
                raise CartError("Cart not found")

            product = await Product.get(product_id)
            variant = next((v for v in product.variants if v.sku == sku), None) if product else None
            
            if not variant:
                raise VariantNotFound("Variant no longer exists.")
            if data.quantity > variant.stock:
                raise StockExceeded(f"Only {variant.stock} in stock.")

            new_items = []
            found = False
            for item in cart.items:
                if item.product_id == product_id and item.sku == sku:
                    found = True
                    new_item = item.model_copy()
                    new_item.quantity = data.quantity
                    new_items.append(new_item)
                else:
                    new_items.append(item.model_copy())

            if not found:
                raise CartError("Item not found in cart.")

            collection = Cart.get_pymongo_collection() # type: ignore
            update_result = await collection.update_one(
                {"_id": cart.id, "version": cart.version},
                {
                    "$set": {"items": [i.model_dump() for i in new_items], "updated_at": datetime.utcnow()},
                    "$inc": {"version": 1}
                }
            )

            if update_result.modified_count > 0:
                updated_cart = await Cart.get(cart.id)
                if updated_cart:
                    return updated_cart
                
            await asyncio.sleep(0.01 * (attempt + 1))

        raise CartConflictError("Cart was modified concurrently. Please retry.")

    @staticmethod
    async def remove_from_cart(user_id: PydanticObjectId, product_id: PydanticObjectId, sku: str) -> Cart:
        for attempt in range(CartService.MAX_RETRIES):
            cart = await Cart.find_one(Cart.user_id == user_id)
            if not cart:
                raise CartError("Cart not found")

            new_items = [i for i in cart.items if not (i.product_id == product_id and i.sku == sku)]
            
            if len(new_items) == len(cart.items):
                raise CartError("Item not found in cart.")

            collection = Cart.get_pymongo_collection() # type: ignore
            update_result = await collection.update_one(
                {"_id": cart.id, "version": cart.version},
                {
                    "$set": {"items": [i.model_dump() for i in new_items], "updated_at": datetime.utcnow()},
                    "$inc": {"version": 1}
                }
            )

            if update_result.modified_count > 0:
                updated_cart = await Cart.get(cart.id)
                if updated_cart:
                    return updated_cart
                
            await asyncio.sleep(0.01 * (attempt + 1))

        raise CartConflictError("Cart was modified concurrently. Please retry.")

    @staticmethod
    async def get_cart(user_id: PydanticObjectId) -> CartResponse:
        cart = await Cart.find_one(Cart.user_id == user_id)
        if not cart or not cart.items:
            return CartResponse(items=[], total_quantity=0, total_price=0)

        product_ids = list(set(i.product_id for i in cart.items))
        products = await Product.find({"_id": {"$in": product_ids}}).to_list()
        p_map = {str(p.id): p for p in products}

        detailed_items = []
        t_price, t_qty = 0, 0

        for item in cart.items:
            product = p_map.get(str(item.product_id))
            
            is_available = True
            available_stock = 0
            subtotal = 0
            variant_response = None
            effective_qty = 0
            
            if not product or getattr(product, "is_deleted", False) or not getattr(product, "is_available", True):
                is_available = False
            else:
                variant = next((v for v in product.variants if v.sku == item.sku), None)
                if not variant or variant.stock <= 0:
                    is_available = False
                else:
                    available_stock = variant.stock
                    variant_response = ProductVariantResponse(**variant.model_dump())
                    
                    effective_qty = min(item.quantity, available_stock)
                    subtotal = variant.effective_price * effective_qty
                    t_price += subtotal
                    t_qty += effective_qty

            detailed_items.append(CartItemDetailed(
                product_id=item.product_id,
                name=product.name if product else "Unavailable Product",
                brand=product.brand if product else "",
                sku=item.sku,
                image=product.images[0] if product and product.images else None,
                variant=variant_response,
                requested_quantity=item.quantity,
                effective_quantity=effective_qty,
                subtotal=subtotal,
                is_available=is_available,
                available_stock=available_stock
            ))

        return CartResponse(items=detailed_items, total_quantity=t_qty, total_price=t_price)