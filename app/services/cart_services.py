from typing import Optional, List
from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.models.cart_model import Cart, CartItem
from app.models.product_model import Product
from app.schemas.cart_schema import (
    CartItemAdd,
    CartItemUpdate,
    CartResponse,
    CartItemDetailed,
)
from app.schemas.product_variant_schema import ProductVariantResponse

class CartService:
    MAX_CART_ITEMS = 20

    @staticmethod
    async def get_or_create_cart(user_id: PydanticObjectId) -> Cart:
        cart = await Cart.find_one(Cart.user_id == user_id)
        if not cart:
            cart = Cart(user_id=user_id, items=[])
            await cart.insert()
        return cart

    @staticmethod
    def _find_variant(product: Product, sku: str):
        return next((v for v in product.variants if v.sku == sku), None)

    @staticmethod
    def _validate_product_for_cart(product: Optional[Product]) -> Product:
        if not product or getattr(product, "is_deleted", False):
            raise HTTPException(status_code=404, detail="Product not found or deleted")
        if not getattr(product, "is_available", True):
            raise HTTPException(status_code=400, detail="Product is currently unavailable")
        return product

    @staticmethod
    def _find_cart_item(cart: Cart, product_id: PydanticObjectId, sku: str):
        return next((i for i in cart.items if i.product_id == product_id and i.sku == sku), None)

    @staticmethod
    async def add_to_cart(user_id: PydanticObjectId, data: CartItemAdd) -> Cart:
        product = await Product.get(data.product_id)
        product = CartService._validate_product_for_cart(product)
        variant = next((v for v in product.variants if v.sku == data.sku), None)
        
        if not variant:
            raise HTTPException(status_code=404, detail="Variant (SKU) not found")

        cart = await CartService.get_or_create_cart(user_id)
        existing_item = CartService._find_cart_item(cart, data.product_id, data.sku)

        if not existing_item and len(cart.items) >= CartService.MAX_CART_ITEMS:
            raise HTTPException(status_code=400, detail="Cart limit reached (max 50 unique items)")

        new_qty = (existing_item.quantity + data.quantity) if existing_item else data.quantity
        
        if new_qty > variant.stock:
            raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {variant.stock}")

        if existing_item:
            existing_item.quantity = new_qty
        else:
            cart.items.append(CartItem(**data.model_dump()))

        await cart.save()
        return cart

    @staticmethod
    async def update_item_quantity(user_id: PydanticObjectId, product_id: PydanticObjectId, sku: str, data: CartItemUpdate) -> Cart:
        cart = await Cart.find_one(Cart.user_id == user_id)
        if not cart: raise HTTPException(status_code=404, detail="Cart not found")

        product = await Product.get(product_id)
        product = CartService._validate_product_for_cart(product)
        variant = CartService._find_variant(product, sku)
        
        if not variant: raise HTTPException(status_code=404, detail="SKU no longer exists")
        if data.quantity > variant.stock:
            raise HTTPException(status_code=400, detail=f"Only {variant.stock} in stock")

        item = CartService._find_cart_item(cart, product_id, sku)
        if not item: raise HTTPException(status_code=404, detail="Item not in cart")

        item.quantity = data.quantity
        await cart.save()
        return cart

    @staticmethod
    async def remove_from_cart(user_id: PydanticObjectId, product_id: PydanticObjectId, sku: str) -> Cart:
        cart = await Cart.find_one(Cart.user_id == user_id)
        if not cart: raise HTTPException(status_code=404, detail="Cart not found")

        initial_len = len(cart.items)
        cart.items = [i for i in cart.items if not (i.product_id == product_id and i.sku == sku)]
        
        if len(cart.items) == initial_len:
            raise HTTPException(status_code=404, detail="Item not found")

        await cart.save()
        return cart

    @staticmethod
    async def get_cart(user_id: PydanticObjectId) -> CartResponse:
        cart = await Cart.find_one(Cart.user_id == user_id)
        if not cart or not cart.items:
            return CartResponse(items=[], total_quantity=0, total_price=0)

        product_ids = list(set(i.product_id for i in cart.items))
        products = await Product.find({"_id": {"$in": product_ids}}).to_list()
        p_map = {str(p.id): p for p in products}

        detailed_items, valid_items = [], []
        t_price, t_qty = 0, 0

        for item in cart.items:
            product = p_map.get(str(item.product_id))
            if not product or getattr(product, "is_deleted", False) or not getattr(product, "is_available", True):
                continue

            variant = CartService._find_variant(product, item.sku)
            if not variant or variant.stock <= 0:
                continue

            # Auto-correction for stock drops
            qty = min(item.quantity, variant.stock)
            subtotal = variant.price * qty
            t_price += subtotal
            t_qty += qty

            valid_items.append(CartItem(product_id=item.product_id, sku=item.sku, quantity=qty))
            detailed_items.append(CartItemDetailed(
                product_id=item.product_id, name=product.name, brand=product.brand,
                sku=item.sku, image=product.images[0] if product.images else None,
                variant=ProductVariantResponse(**variant.model_dump()),
                quantity=qty, subtotal=subtotal
            ))

        # Sync database if stale items were cleaned
        if len(valid_items) != len(cart.items):
            cart.items = valid_items
            await cart.save()

        return CartResponse(items=detailed_items, total_quantity=t_qty, total_price=t_price)