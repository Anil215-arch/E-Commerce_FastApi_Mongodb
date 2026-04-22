from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import DomainValidationError
from app.schemas.inventory_schema import InventoryVariantResponse
from app.services.inventory_services import InventoryService


@pytest.mark.asyncio
async def test_adjust_available_stock_writes_inventory_ledger_entry():
    product_id = PydanticObjectId()
    seller_id = PydanticObjectId()

    class _TransactionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _SessionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def start_transaction(self):
            return _TransactionContext()

    fake_client = SimpleNamespace(start_session=Mock(return_value=_SessionContext()))
    fake_collection = SimpleNamespace(
        database=SimpleNamespace(client=fake_client),
        find_one_and_update=AsyncMock(
            return_value={
                "variants": [
                    {
                        "sku": "SKU-LEDGER-1",
                        "available_stock": 10,
                        "reserved_stock": 2,
                    }
                ]
            }
        )
    )
    fake_ledger_collection = SimpleNamespace(insert_one=AsyncMock())

    with patch("app.services.inventory_services.Product.get_pymongo_collection", return_value=fake_collection):
        with patch("app.services.inventory_services.InventoryLedger.get_pymongo_collection", return_value=fake_ledger_collection):
            with patch(
                "app.services.inventory_services.InventoryService.get_variant_inventory",
                new=AsyncMock(
                    return_value=InventoryVariantResponse(
                        product_id=product_id,
                        sku="SKU-LEDGER-1",
                        available_stock=15,
                        reserved_stock=2,
                        total_stock=17,
                    )
                ),
            ):
                result = await InventoryService.adjust_available_stock(
                    product_id=product_id,
                    sku="SKU-LEDGER-1",
                    owner_seller_id=seller_id,
                    actor_user_id=seller_id,
                    request_id="req-ledger-001",
                    delta=5,
                    reason="restock from supplier",
                )

    assert result.available_stock == 15
    assert result.total_stock == 17
    fake_ledger_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_adjust_available_stock_is_idempotent_on_duplicate_request_id():
    product_id = PydanticObjectId()
    seller_id = PydanticObjectId()

    class _TransactionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _SessionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def start_transaction(self):
            return _TransactionContext()

    fake_client = SimpleNamespace(start_session=Mock(return_value=_SessionContext()))
    fake_collection = SimpleNamespace(
        database=SimpleNamespace(client=fake_client),
        find_one_and_update=AsyncMock(return_value={"variants": [{"sku": "SKU-LEDGER-3", "available_stock": 20}]}),
    )
    fake_ledger_collection = SimpleNamespace(
        insert_one=AsyncMock(side_effect=DuplicateKeyError("duplicate request_id")),
        find_one=AsyncMock(return_value={"delta": -2, "reason": "manual correction"}),
    )

    with patch("app.services.inventory_services.Product.get_pymongo_collection", return_value=fake_collection):
        with patch("app.services.inventory_services.InventoryLedger.get_pymongo_collection", return_value=fake_ledger_collection):
            with patch(
                "app.services.inventory_services.InventoryService.get_variant_inventory",
                new=AsyncMock(
                    return_value=InventoryVariantResponse(
                        product_id=product_id,
                        sku="SKU-LEDGER-3",
                        available_stock=20,
                        reserved_stock=1,
                        total_stock=21,
                    )
                ),
            ):
                result = await InventoryService.adjust_available_stock(
                    product_id=product_id,
                    sku="SKU-LEDGER-3",
                    owner_seller_id=seller_id,
                    actor_user_id=seller_id,
                    request_id="req-ledger-duplicate",
                    delta=-2,
                    reason="manual correction",
                )

    assert result.available_stock == 20
    fake_ledger_collection.find_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_adjust_available_stock_rejects_when_decrement_exceeds_available_stock():
    product_id = PydanticObjectId()
    seller_id = PydanticObjectId()

    class _TransactionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _SessionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def start_transaction(self):
            return _TransactionContext()

    fake_client = SimpleNamespace(start_session=Mock(return_value=_SessionContext()))
    fake_collection = SimpleNamespace(
        database=SimpleNamespace(client=fake_client),
        find_one_and_update=AsyncMock(return_value=None)
    )
    fake_ledger_collection = SimpleNamespace(insert_one=AsyncMock())

    with patch("app.services.inventory_services.Product.get_pymongo_collection", return_value=fake_collection):
        with patch("app.services.inventory_services.InventoryLedger.get_pymongo_collection", return_value=fake_ledger_collection):
            with pytest.raises(HTTPException) as exc:
                await InventoryService.adjust_available_stock(
                    product_id=product_id,
                    sku="SKU-LEDGER-2",
                    owner_seller_id=seller_id,
                    actor_user_id=seller_id,
                    request_id="req-ledger-002",
                    delta=-20,
                    reason="damage write-off",
                )

    assert exc.value.status_code == 409
    fake_ledger_collection.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_adjust_available_stock_rejects_short_request_id_before_db_calls():
    with pytest.raises(DomainValidationError) as exc:
        await InventoryService.adjust_available_stock(
            product_id=PydanticObjectId(),
            sku="SKU-VALID-1",
            owner_seller_id=PydanticObjectId(),
            actor_user_id=PydanticObjectId(),
            request_id="short",
            delta=5,
            reason="manual adjustment",
        )

    assert "request_id" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_reserve_stock_rejects_non_positive_quantity_before_db_calls():
    with pytest.raises(DomainValidationError) as exc:
        await InventoryService.reserve_stock(
            product_id=PydanticObjectId(),
            sku="SKU-VALID-1",
            quantity=0,
        )

    assert "strictly positive" in str(exc.value).lower()
