from fastapi import HTTPException, status
from beanie import PydanticObjectId
from app.models.cart_model import Cart
from app.models.product_model import Product
from app.models.order_model import Order, OrderItemSnapshot, OrderStatus
from app.schemas.order_schema import CheckoutRequest, OrderResponse, OrderUpdateStatusRequest
from app.models.user_model import User
from app.core.user_role import UserRole

class OrderService:
    @staticmethod
    async def checkout(user_id: PydanticObjectId, data: CheckoutRequest) -> OrderResponse:
        cart = await Cart.find_one(Cart.user_id == user_id)
        if not cart or not cart.items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

        order_items = []
        subtotal = 0  

        # 1. Fetch all products in the cart
        product_ids = list(set(item.product_id for item in cart.items))
        products = await Product.find({"_id": {"$in": product_ids}}).to_list()
        product_map = {str(p.id): p for p in products}

        # 2. Validate, Snapshot, and Deduct
        for cart_item in cart.items:
            product = product_map.get(str(cart_item.product_id))
            if not product or getattr(product, "is_deleted", False) or not getattr(product, "is_available", True):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Product {cart_item.product_id} is unavailable"
                )
            
            variant = next((v for v in product.variants if v.sku == cart_item.sku), None)
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Variant {cart_item.sku} not found"
                )
            
            if cart_item.quantity > variant.stock:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Insufficient stock for {cart_item.sku}. Available: {variant.stock}"
                )

            # Snapshot the price using the mathematically sound effective_price property
            purchase_price = variant.effective_price
            item_total = purchase_price * cart_item.quantity
            subtotal += item_total

            # Deduct stock locally
            variant.stock -= cart_item.quantity

            order_items.append(OrderItemSnapshot(
                product_id=cart_item.product_id,
                sku=cart_item.sku,
                quantity=cart_item.quantity,
                purchase_price=purchase_price
            ))

        # 3. Persist stock deductions
        for product in products:
            await product.save()

        # 4. Commerce Math Engine (Server-Side Enforcement)
        # Using 18% tax and a 1000 threshold for free shipping as an example.
        # Everything is cast to int to prevent floating point crashes.
        tax_amount = int(subtotal * 0.18)
        shipping_fee = 0 if subtotal > 1000 else 50
        grand_total = subtotal + tax_amount + shipping_fee

        # 5. Generate the Order
        new_order = Order(
            user_id=user_id,
            items=order_items,
            shipping_address=data.shipping_address,
            billing_address=data.billing_address,
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_fee=shipping_fee,
            grand_total=grand_total,
            status=OrderStatus.PENDING,
            created_by=user_id,
            updated_by=user_id
        )
        await new_order.insert()

        # 6. Clear the Cart
        cart.items = []
        await cart.save()

        return OrderResponse.model_validate(new_order)
    
    @staticmethod
    async def get_my_orders(user_id: PydanticObjectId) -> list[OrderResponse]:
        """Fetches all orders for a specific user, sorted by newest first."""
        
        orders = await Order.find(Order.user_id == user_id).sort("-created_at").to_list()
        return [OrderResponse.model_validate(order) for order in orders]

    @staticmethod
    async def get_order_by_id(user_id: PydanticObjectId, order_id: PydanticObjectId) -> OrderResponse:
        """Fetches a specific order, strictly enforcing user ownership."""
        
        order = await Order.find_one((Order.id == order_id) & (Order.user_id == user_id))
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Order not found or you do not have permission to view it"
            )
            
        return OrderResponse.model_validate(order)
    @staticmethod
    async def update_order_status(
        order_id: PydanticObjectId, 
        data: OrderUpdateStatusRequest, 
        current_user: User
    ) -> OrderResponse:
        """Function to update the fulfillment status of an order."""
        order = await Order.get(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Order not found"
            )

        # 1. Authorization: ADMIN passes. SELLER must be verified.
        if current_user.role == UserRole.SELLER:
            # Fetch the products in this order to check 'created_by' (the Seller)
            product_ids = [item.product_id for item in order.items]
            products = await Product.find({"_id": {"$in": product_ids}}).to_list()
            
            # Check if this seller owns ANY of the products in this order
            is_owner = any(p.created_by == current_user.id for p in products)
            
            if not is_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="You do not have permission to manage this order. It contains no products owned by you."
                )

        # 2. State Machine Validation
        if order.status == OrderStatus.CANCELLED or order.status == OrderStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change status of an order that is already {order.status.value}"
            )

        # 3. Execution & Audit
        order.status = data.status
        order.updated_by = current_user.id
        await order.save()
        
        return OrderResponse.model_validate(order)