import asyncio
import random
import uuid
import logging
import traceback
from datetime import datetime, timedelta, timezone
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
from app.services.inventory_services import InventoryService
from app.validators.order_validator import OrderDomainValidator
from app.validators.transaction_validator import TransactionDomainValidator

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
    CHECKOUT_EXPIRY_MINUTES = 15
    EXPIRY_CLEANUP_INTERVAL_SECONDS = 60
    ALLOWED_STATUS_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
        OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
        OrderStatus.CONFIRMED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
        OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
        OrderStatus.DELIVERED: {OrderStatus.COMPLETED},
        OrderStatus.COMPLETED: set(),
        OrderStatus.CANCELLED: set(),
    }

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

            if variant.available_stock < cart_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Insufficient stock for {product.name} ({cart_item.sku}). "
                        f"Requested {cart_item.quantity}, available {variant.available_stock}."
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
    async def _build_checkout_batch_response(existing_orders: list[Order]) -> CheckoutBatchResponse:
        if not existing_orders:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No orders found for checkout batch.",
            )

        transaction = await Transaction.find_one({"_id": existing_orders[0].transaction_id})
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Checkout batch is missing transaction data.",
            )
        if transaction.id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Checkout batch transaction has no identifier.",
            )

        return CheckoutBatchResponse(
            checkout_batch_id=existing_orders[0].checkout_batch_id,
            transaction_id=transaction.id,
            amount=transaction.amount,
            transaction_status=transaction.status,
            payment_method=transaction.payment_method,
            orders=[OrderResponse.model_validate(order) for order in existing_orders],
        )

    @staticmethod
    async def _mark_checkout_failed(
        transaction: Transaction | None,
        orders: list[Order],
        user_id: PydanticObjectId
    ) -> None:
        """
        Idempotent failure finalization.
        Ensures no zombie PENDING records remain.
        """

        if transaction and transaction.status == TransactionStatus.PENDING:
            transaction.status = TransactionStatus.FAILED
            transaction.updated_by = user_id
            await transaction.save()

        for order in orders:
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                if order.payment_status == OrderPaymentStatus.PENDING:
                    order.payment_status = OrderPaymentStatus.FAILED
                order.expires_at = None
                order.updated_by = user_id
                await order.save()

    @staticmethod
    async def cleanup_expired_orders() -> None:
        now = datetime.now(timezone.utc)
        expired_orders = await Order.find(
            {
                "status": OrderStatus.PENDING,
                "cleanup_processed": False,
                "expires_at": {"$lte": now},
                "is_deleted": {"$ne": True},
            }
        ).to_list()

        touched_transactions: set[str] = set()
        for order in expired_orders:
            for item in order.items:
                await InventoryService.release_reserved_stock(
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity,
                )

            order.status = OrderStatus.CANCELLED
            order.payment_status = OrderPaymentStatus.FAILED
            order.cancellation_reason = "Checkout session expired."
            order.expires_at = None
            order.cleanup_processed = True
            await order.save()

            transaction_key = str(order.transaction_id)
            if transaction_key in touched_transactions:
                continue

            touched_transactions.add(transaction_key)
            transaction = await Transaction.find_one({"_id": order.transaction_id})
            if transaction and transaction.status == TransactionStatus.PENDING:
                transaction.status = TransactionStatus.FAILED
                await transaction.save()

    @staticmethod
    async def run_cleanup_loop() -> None:
        while True:
            try:
                await OrderService.cleanup_expired_orders()
            except Exception:
                logger.exception("Expired order cleanup loop failed")
            await asyncio.sleep(OrderService.EXPIRY_CLEANUP_INTERVAL_SECONDS)

    @staticmethod
    async def checkout(user_id: PydanticObjectId, data: CheckoutRequest) -> CheckoutBatchResponse:
        user = await User.get(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        OrderDomainValidator.validate_checkout_request(
            checkout_batch_id=data.checkout_batch_id,
            shipping_index=data.shipping_address_index,
            billing_index=data.billing_address_index
        )
        checkout_batch_id = data.checkout_batch_id
        existing_orders = await Order.find(
            {
                "checkout_batch_id": checkout_batch_id,
                "user_id": user_id,
                "is_deleted": {"$ne": True},
            }
        ).to_list()
        if existing_orders:
            return await OrderService._build_checkout_batch_response(existing_orders)

        try:
            extracted_shipping = user.addresses[data.shipping_address_index]
            extracted_billing = user.addresses[data.billing_address_index]
        except IndexError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid shipping or billing address index. Address does not exist."
            )
            
        checkout_items = await OrderService._load_checkout_items(user_id)
        TransactionDomainValidator.validate_checkout_items(checkout_items)
        if not checkout_items:
            raise HTTPException(status_code=400, detail="No valid items for checkout")
        
        seller_groups = OrderService._group_items_by_seller(checkout_items)

        reserved_items: list[OrderItemSnapshot] = []
        created_orders: list[Order] = []
        created_transaction: Transaction | None = None
        payment_captured = False
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=OrderService.CHECKOUT_EXPIRY_MINUTES)

        try:

            for item in checkout_items:
                await InventoryService.reserve_stock(
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity
                )
                reserved_items.append(item)

            seller_order_payloads: list[SellerOrderPayload] = []
            transaction_amount = 0
            for group in seller_groups:
                subtotal = group["subtotal"]
                tax_amount, shipping_fee, grand_total = OrderService._calculate_order_totals(subtotal)
                OrderDomainValidator.validate_financial_math(
                    subtotal=subtotal, 
                    tax=tax_amount, 
                    shipping=shipping_fee, 
                    grand_total=grand_total
                )
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
                    shipping_address=extracted_shipping,
                    billing_address=extracted_billing,
                    subtotal=payload["subtotal"],  # type: ignore[arg-type]
                    tax_amount=payload["tax_amount"],  # type: ignore[arg-type]
                    shipping_fee=payload["shipping_fee"],  # type: ignore[arg-type]
                    grand_total=payload["grand_total"],  # type: ignore[arg-type]
                    status=OrderStatus.PENDING,
                    payment_status=OrderPaymentStatus.PENDING,
                    expires_at=expires_at,
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
            TransactionDomainValidator.validate_allocations(
                total_amount=created_transaction.amount, 
                allocations=created_transaction.allocations
            )
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
            for item in reserved_items:
                await InventoryService.confirm_stock_deduction(
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity
                )
            created_transaction.status = TransactionStatus.SUCCESS
            created_transaction.gateway_transaction_id = payment_result["txn_id"]
            created_transaction.updated_by = user_id
            await created_transaction.save()
 
            for order in created_orders:
                order.status = OrderStatus.CONFIRMED
                order.payment_status = OrderPaymentStatus.PAID
                order.expires_at = None
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
                for item in reserved_items:
                    await InventoryService.release_reserved_stock(
                        product_id=item.product_id,
                        sku=item.sku,
                        quantity=item.quantity
                    )
                await OrderService._mark_checkout_failed(created_transaction, created_orders, user_id)
            raise
        except Exception:
            if payment_captured:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Payment was captured, but order finalization needs manual review.",
                )

            for item in reserved_items:
                await InventoryService.release_reserved_stock(
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity
                )
            await OrderService._mark_checkout_failed(created_transaction, created_orders, user_id)
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
        reason = OrderDomainValidator.validate_cancellation_reason(reason)
        order = await Order.find_one({"_id": order_id, "is_deleted": {"$ne": True}})
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        original_payment_status = order.payment_status

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

        # Guard against the brief partial-finalization window after payment capture.
        if order.payment_status == OrderPaymentStatus.PAID and order.status != OrderStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order is currently finalizing. Please retry cancellation in a few moments."
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
                    TransactionDomainValidator.validate_refund_math(
                        total_amount=transaction.amount,
                        total_refunded=transaction.refunded_amount,
                        allocations=transaction.allocations
                    )
            elif transaction.status == TransactionStatus.PENDING:
                transaction.status = TransactionStatus.FAILED
                order.payment_status = OrderPaymentStatus.FAILED

            transaction.updated_by = current_user.id
            await transaction.save()

        for item in order.items:
            if original_payment_status == OrderPaymentStatus.PENDING:
                await InventoryService.release_reserved_stock(
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity
                )
            else:
                await InventoryService.restore_stock(
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity
                )

        order.status = OrderStatus.CANCELLED
        order.cancellation_reason = reason # Persist the audit trail
        order.expires_at = None
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
