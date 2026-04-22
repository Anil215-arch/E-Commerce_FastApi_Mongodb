from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.core.exceptions import DomainValidationError
from app.models.email_otp_model import OTPPurpose
from app.models.cart_model import CartItem
from app.models.product_variant_model import ProductVariant
from app.schemas.cart_schema import CartItemAdd, CartItemUpdate
from app.services.cart_services import (
    CartLimitExceeded,
    CartService,
    ProductUnavailable,
    StockExceeded,
)
from app.services.email_otp_services import OTPService


@pytest.fixture(autouse=True)
def _stub_beanie_expression_fields():
    with patch("app.services.cart_services.Cart.user_id", new=object(), create=True):
        with patch("app.services.email_otp_services.EmailOTPVerification.email", new=object(), create=True):
            with patch("app.services.email_otp_services.EmailOTPVerification.purpose", new=object(), create=True):
                yield


@pytest.mark.asyncio
async def test_add_to_cart_rejects_when_unique_item_limit_is_reached():
    user_id = PydanticObjectId()
    new_product_id = PydanticObjectId()

    existing_items = [CartItem(product_id=PydanticObjectId(), sku=f"SKU{i}", quantity=1) for i in range(CartService.MAX_CART_ITEMS)]
    cart = SimpleNamespace(items=existing_items, save=AsyncMock())
    product = SimpleNamespace(
        id=new_product_id,
        is_deleted=False,
        is_available=True,
        variants=[SimpleNamespace(sku="SKU-NEW", available_stock=10)],
    )

    with patch("app.services.cart_services.Product.get", new=AsyncMock(return_value=product)):
        with patch("app.services.cart_services.CartService.get_or_create_cart", new=AsyncMock(return_value=cart)):
            with pytest.raises(CartLimitExceeded) as exc:
                await CartService.add_to_cart(
                    user_id,
                    CartItemAdd(product_id=new_product_id, sku="SKU-NEW", quantity=1),
                )

    assert "Cart limit reached" in str(exc.value)


@pytest.mark.asyncio
async def test_add_to_cart_rejects_when_requested_quantity_exceeds_stock():
    user_id = PydanticObjectId()
    product_id = PydanticObjectId()

    existing_item = CartItem(product_id=product_id, sku="SKU-1", quantity=3)
    cart = SimpleNamespace(items=[existing_item], save=AsyncMock())
    product = SimpleNamespace(
        id=product_id,
        is_deleted=False,
        is_available=True,
        variants=[SimpleNamespace(sku="SKU-1", available_stock=4)],
    )

    with patch("app.services.cart_services.Product.get", new=AsyncMock(return_value=product)):
        with patch("app.services.cart_services.CartService.get_or_create_cart", new=AsyncMock(return_value=cart)):
            with pytest.raises(StockExceeded) as exc:
                await CartService.add_to_cart(
                    user_id,
                    CartItemAdd(product_id=product_id, sku="SKU-1", quantity=2),
                )

    assert "Insufficient stock" in str(exc.value)


@pytest.mark.asyncio
async def test_get_cart_cleans_stale_items_and_mutates_storage_on_read():
    user_id = PydanticObjectId()
    valid_product_id = PydanticObjectId()
    removed_product_id = PydanticObjectId()

    cart = SimpleNamespace(
        items=[
            CartItem(product_id=valid_product_id, sku="A-1", quantity=5),
            CartItem(product_id=removed_product_id, sku="B-1", quantity=2),
        ],
        save=AsyncMock(),
    )
    valid_variant = ProductVariant(sku="A-1", price=100, discount_price=80, available_stock=3)
    valid_product = SimpleNamespace(
        id=valid_product_id,
        name="Laptop",
        brand="Brand",
        images=[],
        is_deleted=False,
        is_available=True,
        variants=[valid_variant],
    )
    find_cursor = SimpleNamespace(to_list=AsyncMock(return_value=[valid_product]))

    with patch("app.services.cart_services.Cart.find_one", new=AsyncMock(return_value=cart)):
        with patch("app.services.cart_services.Product.find", return_value=find_cursor):
            result = await CartService.get_cart(user_id)

    assert result.total_quantity == 3
    assert result.total_price == 240
    assert len(result.items) == 2
    assert result.items[0].sku == "A-1"
    assert result.items[1].sku == "B-1"
    assert result.items[1].is_available is False
    cart.save.assert_not_called()


@pytest.mark.asyncio
async def test_update_item_quantity_rejects_when_new_quantity_exceeds_stock():
    user_id = PydanticObjectId()
    product_id = PydanticObjectId()
    cart = SimpleNamespace(
        items=[CartItem(product_id=product_id, sku="SKU-2", quantity=1)],
        save=AsyncMock(),
    )
    product = SimpleNamespace(
        is_deleted=False,
        is_available=True,
        variants=[SimpleNamespace(sku="SKU-2", available_stock=2)],
    )

    with patch("app.services.cart_services.Cart.find_one", new=AsyncMock(return_value=cart)):
        with patch("app.services.cart_services.Product.get", new=AsyncMock(return_value=product)):
            with pytest.raises(StockExceeded) as exc:
                await CartService.update_item_quantity(
                    user_id,
                    product_id,
                    "SKU-2",
                    CartItemUpdate(quantity=5),
                )

    assert "Only 2 in stock" in str(exc.value)


@pytest.mark.asyncio
async def test_add_to_cart_rejects_deleted_or_unavailable_product():
    user_id = PydanticObjectId()
    product_id = PydanticObjectId()
    cart = SimpleNamespace(items=[])

    with patch("app.services.cart_services.CartService.get_or_create_cart", new=AsyncMock(return_value=cart)):
        with patch("app.services.cart_services.Product.get", new=AsyncMock(return_value=None)):
            with pytest.raises(ProductUnavailable) as exc:
                await CartService.add_to_cart(
                    user_id,
                    CartItemAdd(product_id=product_id, sku="SKU-1", quantity=1),
                )

    assert "unavailable" in str(exc.value).lower()


def test_as_utc_aware_normalizes_naive_datetime():
    naive = datetime(2026, 4, 10, 12, 30, 0)
    aware = OTPService._as_utc_aware(naive)
    assert aware.tzinfo is not None
    assert aware.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_verify_otp_deletes_document_when_expired():
    otp_doc = SimpleNamespace(
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        delete=AsyncMock(),
        save=AsyncMock(),
        hashed_otp="ignored",
        attempts=0,
    )

    with patch("app.services.email_otp_services.EmailOTPVerification.find_one", new=AsyncMock(return_value=otp_doc)):
        with pytest.raises(DomainValidationError) as exc:
            await OTPService.verify_otp("user@example.com", "123456", OTPPurpose.REGISTRATION)

    assert "expired" in str(exc.value).lower()
    otp_doc.delete.assert_awaited_once()
    otp_doc.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_otp_rejects_invalid_code_without_deleting_document():
    otp_doc = SimpleNamespace(
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        delete=AsyncMock(),
        save=AsyncMock(),
        hashed_otp="hashed",
        attempts=0,
    )

    with patch("app.services.email_otp_services.EmailOTPVerification.find_one", new=AsyncMock(return_value=otp_doc)):
        with patch("app.services.email_otp_services.OTPService._verify_otp_hash", return_value=False):
            with pytest.raises(DomainValidationError) as exc:
                await OTPService.verify_otp("user@example.com", "000000", OTPPurpose.PASSWORD_RESET)

    assert "invalid otp code" in str(exc.value).lower()
    assert otp_doc.attempts == 1
    otp_doc.delete.assert_not_called()
    otp_doc.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_otp_accepts_valid_code_and_deletes_document():
    otp_doc = SimpleNamespace(
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        delete=AsyncMock(),
        save=AsyncMock(),
        hashed_otp="hashed",
        attempts=0,
    )

    with patch("app.services.email_otp_services.EmailOTPVerification.find_one", new=AsyncMock(return_value=otp_doc)):
        with patch("app.services.email_otp_services.OTPService._verify_otp_hash", return_value=True):
            assert await OTPService.verify_otp("user@example.com", "123456", OTPPurpose.REGISTRATION) is True

    otp_doc.delete.assert_awaited_once()
    otp_doc.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_and_send_otp_replaces_previous_record_and_dispatches_email():
    created_doc = SimpleNamespace(insert=AsyncMock())
    otp_model = MagicMock()
    otp_model.find_one = AsyncMock(return_value=None)
    otp_model.return_value = created_doc

    with patch("app.services.email_otp_services.EmailOTPVerification", otp_model):
        with patch("app.services.email_otp_services.OTPService._generate_otp_code", return_value="123456"):
            with patch("app.services.email_otp_services.OTPService._hash_otp", return_value="hashed-otp"):
                with patch("app.services.email_otp_services.EmailService.send_otp_email", new=AsyncMock()) as mock_send:
                    with patch("builtins.print") as mock_print:
                        await OTPService.create_and_send_otp("user@example.com", OTPPurpose.REGISTRATION)

    otp_model.find_one.assert_awaited_once()
    created_doc.insert.assert_awaited_once()
    mock_send.assert_awaited_once()
    mock_print.assert_not_called()


@pytest.mark.asyncio
async def test_verify_otp_rejects_when_attempt_limit_is_exceeded_and_deletes_doc():
    otp_doc = SimpleNamespace(
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        delete=AsyncMock(),
        save=AsyncMock(),
        hashed_otp="hashed",
        attempts=5,
    )

    with patch("app.services.email_otp_services.EmailOTPVerification.find_one", new=AsyncMock(return_value=otp_doc)):
        with pytest.raises(DomainValidationError) as exc:
            await OTPService.verify_otp("user@example.com", "123456", OTPPurpose.REGISTRATION)

    assert "maximum verification attempts" in str(exc.value).lower()
    otp_doc.delete.assert_awaited_once()
    otp_doc.save.assert_not_awaited()


def test_cart_item_add_schema_rejects_zero_quantity():
    with pytest.raises(Exception):
        CartItemAdd(product_id=PydanticObjectId(), sku="SKU", quantity=0)


def test_cart_item_add_schema_rejects_quantity_above_limit():
    with pytest.raises(Exception):
        CartItemAdd(product_id=PydanticObjectId(), sku="SKU", quantity=11)


def test_cart_item_update_schema_rejects_quantity_above_limit():
    with pytest.raises(Exception):
        CartItemUpdate(quantity=11)


def test_cart_item_add_schema_rejects_invalid_sku_format():
    with pytest.raises(Exception):
        CartItemAdd(product_id=PydanticObjectId(), sku="BAD SKU!*", quantity=1)
