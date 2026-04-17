from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId

from app.core.user_role import UserRole
from app.models.order_model import Order, OrderItemSnapshot, OrderPaymentStatus, OrderStatus
from app.models.transaction_model import (
    PaymentMethod,
    Transaction,
    TransactionAllocation,
    TransactionStatus,
)
from app.models.product_variant_model import ProductVariant
from app.schemas.address_schema import Address
from app.schemas.order_schema import CheckoutRequest
from app.services.order_services import DummyPaymentGateway, OrderService


def _address() -> Address:
    return Address(
        full_name="Test User",
        phone_number="9876543210",
        street_address="221B Baker Street",
        city="Bengaluru",
        postal_code="560001",
        state="Karnataka",
        country="India",
    )


@pytest.mark.asyncio
async def test_load_checkout_items_uses_live_price_and_seller_snapshot():
    user_id = PydanticObjectId()
    product_id = PydanticObjectId()
    seller_id = PydanticObjectId()
    cart = SimpleNamespace(items=[SimpleNamespace(product_id=product_id, sku="SKU-1", quantity=2)])
    product = SimpleNamespace(
        id=product_id,
        name="Laptop",
        is_available=True,
        is_deleted=False,
        created_by=seller_id,
        variants=[ProductVariant(sku="SKU-1", price=1000, discount_price=800, stock=5)],
    )
    find_cursor = SimpleNamespace(to_list=AsyncMock(return_value=[product]))

    with patch("app.services.order_services.Cart.find_one", new=AsyncMock(return_value=cart)):
        with patch("app.services.order_services.Product.find", return_value=find_cursor):
            items = await OrderService._load_checkout_items(user_id)

    assert len(items) == 1
    assert items[0].seller_id == seller_id
    assert items[0].product_name == "Laptop"
    assert items[0].purchase_price == 800
    assert items[0].quantity == 2


@pytest.mark.asyncio
async def test_checkout_creates_one_transaction_and_split_orders_per_seller():
    user_id = PydanticObjectId()
    seller_a = PydanticObjectId()
    seller_b = PydanticObjectId()
    item_a = OrderItemSnapshot(
        product_id=PydanticObjectId(),
        seller_id=seller_a,
        sku="A-1",
        product_name="Laptop",
        quantity=1,
        purchase_price=1000,
    )
    item_b = OrderItemSnapshot(
        product_id=PydanticObjectId(),
        seller_id=seller_b,
        sku="B-1",
        product_name="Mouse",
        quantity=2,
        purchase_price=200,
    )

    async def _tx_insert(self):
        self.id = PydanticObjectId()

    async def _order_insert(self):
        self.id = PydanticObjectId()

    async def _noop_save(self):
        return None

    with patch.object(Transaction, "get_pymongo_collection", return_value=object()):
        with patch.object(Order, "get_pymongo_collection", return_value=object()):
            with patch("app.services.order_services.OrderService._load_checkout_items", new=AsyncMock(return_value=[item_a, item_b])):
                with patch("app.services.order_services.OrderService._reserve_stock", new=AsyncMock(return_value=True)):
                    with patch.object(Transaction, "insert", _tx_insert):
                        with patch.object(Transaction, "save", _noop_save):
                            with patch.object(Order, "insert", _order_insert):
                                with patch.object(Order, "save", _noop_save):
                                    with patch.object(DummyPaymentGateway, "process_payment", new=AsyncMock(return_value={"status": "SUCCESS", "txn_id": "gateway-123"})):
                                        with patch("app.services.order_services.CartService.clear_cart", new=AsyncMock(return_value=True)) as mock_clear:
                                            result = await OrderService.checkout(
                                                user_id,
                                                CheckoutRequest(
                                                    shipping_address=_address(),
                                                    billing_address=_address(),
                                                    payment_method=PaymentMethod.CARD,
                                                ),
                                            )

    assert result.transaction_status == TransactionStatus.SUCCESS
    assert result.amount == 1752
    assert len(result.orders) == 2
    assert {order.seller_id for order in result.orders} == {seller_a, seller_b}
    assert len({order.transaction_id for order in result.orders}) == 1
    mock_clear.assert_awaited_once_with(user_id)


@pytest.mark.asyncio
async def test_cancel_order_applies_partial_refund_to_shared_transaction():
    order_id = PydanticObjectId()
    second_order_id = PydanticObjectId()
    transaction_id = PydanticObjectId()
    customer_id = PydanticObjectId()
    seller_id = PydanticObjectId()
    admin_id = PydanticObjectId()

    with patch.object(Order, "get_pymongo_collection", return_value=object()):
        order = Order(
            user_id=customer_id,
            seller_id=seller_id,
            checkout_batch_id="batch-1",
            transaction_id=transaction_id,
            items=[
                OrderItemSnapshot(
                    product_id=PydanticObjectId(),
                    seller_id=seller_id,
                    sku="SKU-1",
                    product_name="Laptop",
                    quantity=1,
                    purchase_price=400,
                )
            ],
            shipping_address=_address(),
            billing_address=_address(),
            subtotal=400,
            tax_amount=72,
            shipping_fee=50,
            grand_total=522,
            status=OrderStatus.CONFIRMED,
            payment_status=OrderPaymentStatus.PAID,
            created_by=customer_id,
            updated_by=customer_id,
        )
        order.id = order_id

    with patch.object(Transaction, "get_pymongo_collection", return_value=object()):
        transaction = Transaction(
            user_id=customer_id,
            checkout_batch_id="batch-1",
            amount=900,
            refunded_amount=0,
            status=TransactionStatus.SUCCESS,
            payment_method=PaymentMethod.CARD,
            gateway_transaction_id="gateway-123",
            allocations=[
                TransactionAllocation(order_id=order_id, seller_id=seller_id, amount=522, refunded_amount=0),
                TransactionAllocation(order_id=second_order_id, seller_id=PydanticObjectId(), amount=378, refunded_amount=0),
            ],
            created_by=customer_id,
            updated_by=customer_id,
        )
        transaction.id = transaction_id

    async def _noop_save(self):
        return None

    with patch("app.services.order_services.Order.find_one", new=AsyncMock(return_value=order)):
        with patch("app.services.order_services.Transaction.find_one", new=AsyncMock(return_value=transaction)):
            with patch.object(Order, "save", _noop_save):
                with patch.object(Transaction, "save", _noop_save):
                    with patch("app.services.order_services.OrderService._rollback_inventory", new=AsyncMock()) as mock_rollback:
                        result = await OrderService.cancel_order(
                            order_id,
                            SimpleNamespace(id=admin_id, role=UserRole.ADMIN),
                                "Customer requested cancellation before dispatch",
                        )

    assert result.payment_status == OrderPaymentStatus.REFUNDED
    assert result.refunded_amount == 522
    assert transaction.status == TransactionStatus.PARTIALLY_REFUNDED
    assert transaction.refunded_amount == 522
    assert transaction.allocations[0].refunded_amount == 522
    mock_rollback.assert_awaited_once()
