import asyncio
import random
import uuid
import logging
import traceback
from collections import OrderedDict
from typing import TypedDict

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.services.invoice_services import InvoiceService
from app.core.user_role import UserRole
from app.models.cart_model import Cart
from app.models.order_model import Order, OrderItemSnapshot, OrderPaymentStatus, OrderStatus
from app.models.product_model import Product
from app.models.transaction_model import (
    PaymentMethod,
    Transaction,
    TransactionAllocation,
    TransactionStatus,
)
from app.models.user_model import User
from app.schemas.order_schema import CheckoutBatchResponse, CheckoutRequest, OrderResponse, OrderUpdateStatusRequest, OrderCancelRequest
from app.events.bus import EventBus
from app.events.order_events import OrderDeliveredEvent, OrderCancelledEvent
from app.services.cart_services import CartService

logger = logging.getLogger(__name__)

class DummyPaymentGateway:
    """Strategy Pattern: Replace this with StripeClient or RazorpayClient later."""

    @staticmethod
    async def process_payment(amount: int, method: PaymentMethod) -> dict[str, str | None]:
        await asyncio.sleep(1)
        is_success = random.random() < 0.8
        if is_success:
            return {"status": "SUCCESS", "txn_id": f"dummy_txn_{uuid.uuid4().hex[:10]}"}
        return {"status": "FAILED", "txn_id": None}


class SellerGroup(TypedDict):
    seller_id: PydanticObjectId
    items: list[OrderItemSnapshot]
    subtotal: int


class SellerOrderPayload(TypedDict):
    seller_id: PydanticObjectId
    items: list[OrderItemSnapshot]
    subtotal: int
    tax_amount: int
    shipping_fee: int
    grand_total: int


class OrderService:
    TAX_RATE = 0.18
    FREE_SHIPPING_THRESHOLD = 1000
    SHIPPING_FEE = 50
    ALLOWED_STATUS_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
        OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
        OrderStatus.CONFIRMED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
        OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
        OrderStatus.DELIVERED: {OrderStatus.COMPLETED},
        OrderStatus.COMPLETED: set(),
        OrderStatus.CANCELLED: set(),
    }

    @staticmethod
    async def _reserve_stock(product_id: PydanticObjectId, sku: str, quantity: int) -> bool:
        collection = Product.get_pymongo_collection()  # type: ignore
        result = await collection.update_one(
            {
                "_id": product_id,
                "is_deleted": {"$ne": True},
                "is_available": True,
                "variants": {
                    "$elemMatch": {
                        "sku": sku,
                        "stock": {"$gte": quantity},
                    }
                },
            },
            {"$inc": {"variants.$.stock": -quantity}},
        )
        return result.modified_count > 0

    @staticmethod
    async def _rollback_inventory(reserved_items: list[OrderItemSnapshot]) -> None:
        collection = Product.get_pymongo_collection()  # type: ignore
        for item in reserved_items:
            await collection.update_one(
                {"_id": item.product_id, "variants.sku": item.sku},
                {"$inc": {"variants.$.stock": item.quantity}},
            )

    @staticmethod
    async def _load_checkout_items(user_id: PydanticObjectId) -> list[OrderItemSnapshot]:
        cart = await Cart.find_one({"user_id": user_id})
        if not cart or not cart.items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

        product_ids = list({item.product_id for item in cart.items})
        products = await Product.find(
            {"_id": {"$in": product_ids}, "is_deleted": {"$ne": True}}
        ).to_list()
        product_map = {str(product.id): product for product in products}

        checkout_items: list[OrderItemSnapshot] = []
        for cart_item in cart.items:
            product = product_map.get(str(cart_item.product_id))
            if not product or not product.is_available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product for SKU {cart_item.sku} is unavailable or deleted.",
                )

            if product.created_by is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {product.name} is missing seller ownership.",
                )

            variant = next((variant for variant in product.variants if variant.sku == cart_item.sku), None)
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Variant {cart_item.sku} for {product.name} no longer exists.",
                )

            if variant.stock < cart_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Insufficient stock for {product.name} ({cart_item.sku}). "
                        f"Requested {cart_item.quantity}, available {variant.stock}."
                    ),
                )

            checkout_items.append(
                OrderItemSnapshot(
                    product_id=cart_item.product_id,
                    seller_id=product.created_by,
                    sku=cart_item.sku,
                    product_name=product.name,
                    quantity=cart_item.quantity,
                    purchase_price=variant.effective_price,
                )
            )

        return checkout_items

    @staticmethod
    def _group_items_by_seller(items: list[OrderItemSnapshot]) -> list[SellerGroup]:
        grouped: OrderedDict[str, SellerGroup] = OrderedDict()
        for item in items:
            seller_key = str(item.seller_id)
            if seller_key not in grouped:
                grouped[seller_key] = {
                    "seller_id": item.seller_id,
                    "items": [],
                    "subtotal": 0,
                }

            grouped[seller_key]["items"].append(item)
            grouped[seller_key]["subtotal"] = grouped[seller_key]["subtotal"] + (item.purchase_price * item.quantity)

        return list(grouped.values())

    @staticmethod
    def _calculate_order_totals(subtotal: int) -> tuple[int, int, int]:
        tax_amount = int(subtotal * OrderService.TAX_RATE)
        shipping_fee = 0 if subtotal > OrderService.FREE_SHIPPING_THRESHOLD else OrderService.SHIPPING_FEE
        grand_total = subtotal + tax_amount + shipping_fee
        return tax_amount, shipping_fee, grand_total

    @staticmethod
    async def _rollback_checkout(
        transaction: Transaction | None,
        orders: list[Order],
        reserved_items: list[OrderItemSnapshot],
        user_id: PydanticObjectId,
    ) -> None:
        if transaction and transaction.status == TransactionStatus.PENDING:
            transaction.status = TransactionStatus.FAILED
            transaction.updated_by = user_id
            await transaction.save()

        for order in orders:
            order.status = OrderStatus.CANCELLED
            if order.payment_status == OrderPaymentStatus.PENDING:
                order.payment_status = OrderPaymentStatus.FAILED
            order.updated_by = user_id
            await order.save()

        await OrderService._rollback_inventory(reserved_items)

    @staticmethod
    async def checkout(user_id: PydanticObjectId, data: CheckoutRequest) -> CheckoutBatchResponse:
        checkout_items = await OrderService._load_checkout_items(user_id)
        seller_groups = OrderService._group_items_by_seller(checkout_items)

        reserved_items: list[OrderItemSnapshot] = []
        created_orders: list[Order] = []
        created_transaction: Transaction | None = None
        payment_captured = False
        checkout_batch_id = uuid.uuid4().hex

        try:
            for item in checkout_items:
                success = await OrderService._reserve_stock(item.product_id, item.sku, item.quantity)
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Failed to reserve stock for {item.product_name} ({item.sku}).",
                    )
                reserved_items.append(item)

            seller_order_payloads: list[SellerOrderPayload] = []
            transaction_amount = 0
            for group in seller_groups:
                subtotal = group["subtotal"]
                tax_amount, shipping_fee, grand_total = OrderService._calculate_order_totals(subtotal)
                transaction_amount += grand_total
                seller_order_payloads.append(
                    {
                        "seller_id": group["seller_id"],
                        "items": group["items"],
                        "subtotal": subtotal,
                        "tax_amount": tax_amount,
                        "shipping_fee": shipping_fee,
                        "grand_total": grand_total,
                    }
                )

            created_transaction = Transaction(
                user_id=user_id,
                checkout_batch_id=checkout_batch_id,
                amount=transaction_amount,
                payment_method=data.payment_method,
                status=TransactionStatus.PENDING,
                allocations=[],
                created_by=user_id,
                updated_by=user_id,
            )
            await created_transaction.insert()

            if created_transaction.id is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create checkout transaction.")

            allocations: list[TransactionAllocation] = []
            for payload in seller_order_payloads:
                order = Order(
                    user_id=user_id,
                    seller_id=payload["seller_id"],  # type: ignore[arg-type]
                    checkout_batch_id=checkout_batch_id,
                    transaction_id=created_transaction.id,
                    items=payload["items"],  # type: ignore[arg-type]
                    shipping_address=data.shipping_address,
                    billing_address=data.billing_address,
                    subtotal=payload["subtotal"],  # type: ignore[arg-type]
                    tax_amount=payload["tax_amount"],  # type: ignore[arg-type]
                    shipping_fee=payload["shipping_fee"],  # type: ignore[arg-type]
                    grand_total=payload["grand_total"],  # type: ignore[arg-type]
                    status=OrderStatus.PENDING,
                    payment_status=OrderPaymentStatus.PENDING,
                    created_by=user_id,
                    updated_by=user_id,
                )
                await order.insert()
                created_orders.append(order)

                if order.id is None:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create seller order.")

                allocations.append(
                    TransactionAllocation(
                        order_id=order.id,
                        seller_id=order.seller_id,
                        amount=order.grand_total,
                    )
                )

            created_transaction.allocations = allocations
            created_transaction.updated_by = user_id
            await created_transaction.save()

            payment_result = await DummyPaymentGateway.process_payment(
                amount=created_transaction.amount,
                method=data.payment_method,
            )
            if payment_result["status"] != "SUCCESS":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Payment gateway declined the transaction.",
                )

            payment_captured = True
            created_transaction.status = TransactionStatus.SUCCESS
            created_transaction.gateway_transaction_id = payment_result["txn_id"]
            created_transaction.updated_by = user_id
            await created_transaction.save()
 
            for order in created_orders:
                order.status = OrderStatus.CONFIRMED
                order.payment_status = OrderPaymentStatus.PAID
                order.updated_by = user_id
                await order.save()
                
                try:
                    await InvoiceService.create_invoice_from_order(order, created_transaction)
                except Exception as e:
                    logger.error(f"CRITICAL: Failed to generate invoice for Order {order.id}. Error: {str(e)}")
                    print("\n" + "="*50)
                    print(f"INVOICE GENERATION FAILED: {repr(e)}")
                    print("="*50 + "\n")
                    print("\n" + "!"*50)
                    print("CATASTROPHIC CHECKOUT CRASH:")
                    traceback.print_exc() 
                    print("!"*50 + "\n")

            await CartService.clear_cart(user_id)

            return CheckoutBatchResponse(
                checkout_batch_id=checkout_batch_id,
                transaction_id=created_transaction.id,
                amount=created_transaction.amount,
                transaction_status=created_transaction.status,
                payment_method=created_transaction.payment_method,
                orders=[OrderResponse.model_validate(order) for order in created_orders],
            )
        except HTTPException:
            if not payment_captured:
                await OrderService._rollback_checkout(created_transaction, created_orders, reserved_items, user_id)
            raise
        except Exception:
            if payment_captured:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Payment was captured, but order finalization needs manual review.",
                )

            await OrderService._rollback_checkout(created_transaction, created_orders, reserved_items, user_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Checkout failed because the payment gateway is unreachable. Inventory released.",
            )

    @staticmethod
    async def get_my_orders(user_id: PydanticObjectId) -> list[OrderResponse]:
        orders = await Order.find(
            {"user_id": user_id, "is_deleted": {"$ne": True}}
        ).sort("-created_at").to_list()
        return [OrderResponse.model_validate(order) for order in orders]

    @staticmethod
    async def get_order_by_id(user_id: PydanticObjectId, order_id: PydanticObjectId) -> OrderResponse:
        order = await Order.find_one(
            {"_id": order_id, "user_id": user_id, "is_deleted": {"$ne": True}}
        )
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or you do not have permission to view it",
            )
        return OrderResponse.model_validate(order)

    @staticmethod
    def _validate_status_transition(current_status: OrderStatus, next_status: OrderStatus) -> None:
        if current_status == next_status:
            return

        allowed_statuses = OrderService.ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if next_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change order status from {current_status.value} to {next_status.value}.",
            )

    @staticmethod
    async def update_order_status(
        order_id: PydanticObjectId,
        data: OrderUpdateStatusRequest,
        current_user: User,
    ) -> OrderResponse:
        order = await Order.find_one({"_id": order_id, "is_deleted": {"$ne": True}})
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if current_user.role == UserRole.SELLER and order.seller_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to manage this order.",
            )

        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change status of an order that is already {order.status.value}.",
            )

        OrderService._validate_status_transition(order.status, data.status)

        order.status = data.status
        order.updated_by = current_user.id
        await order.save()

        # FIRE THE DELIVERED EVENT
        if order.status == OrderStatus.DELIVERED:
            await EventBus.publish(
                OrderDeliveredEvent(
                    order_id=order_id,
                    user_id=order.user_id
                )
            )

        return OrderResponse.model_validate(order)

    @staticmethod
    async def cancel_order(order_id: PydanticObjectId, current_user: User, reason: str) -> OrderResponse:
        order = await Order.find_one({"_id": order_id, "is_deleted": {"$ne": True}})
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if current_user.role == UserRole.CUSTOMER and order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to cancel this order.",
            )

        if current_user.role == UserRole.SELLER and order.seller_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to cancel this order.",
            )

        if current_user.role == UserRole.SUPPORT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Support users cannot cancel orders.",
            )

        if order.status in {OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.COMPLETED}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This order can no longer be cancelled.",
            )

        if order.status == OrderStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already cancelled.",
            )

        transaction = await Transaction.find_one({"_id": order.transaction_id})
        if transaction:
            if transaction.status in {TransactionStatus.SUCCESS, TransactionStatus.PARTIALLY_REFUNDED}:
                refund_amount = max(order.grand_total - order.refunded_amount, 0)
                if refund_amount > 0:
                    order.refunded_amount += refund_amount
                    order.payment_status = OrderPaymentStatus.REFUNDED
                    transaction.refunded_amount += refund_amount
                    for allocation in transaction.allocations:
                        if allocation.order_id == order.id:
                            allocation.refunded_amount += refund_amount
                            break

                    transaction.status = (
                        TransactionStatus.REFUNDED
                        if transaction.refunded_amount >= transaction.amount
                        else TransactionStatus.PARTIALLY_REFUNDED
                    )
            elif transaction.status == TransactionStatus.PENDING:
                transaction.status = TransactionStatus.FAILED
                order.payment_status = OrderPaymentStatus.FAILED

            transaction.updated_by = current_user.id
            await transaction.save()

        await OrderService._rollback_inventory(order.items)

        order.status = OrderStatus.CANCELLED
        order.cancellation_reason = reason # Persist the audit trail
        if order.payment_status == OrderPaymentStatus.PENDING:
            order.payment_status = OrderPaymentStatus.FAILED
        order.updated_by = current_user.id
        await order.save()

        # FIRE THE CANCELLED EVENT
        await EventBus.publish(
            OrderCancelledEvent(
                order_id=order_id,
                user_id=order.user_id,
                reason=reason
            )
        )

        return OrderResponse.model_validate(order)