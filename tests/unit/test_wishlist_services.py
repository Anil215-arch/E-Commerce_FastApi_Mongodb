from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import DomainValidationError
from app.models.product_variant_model import ProductVariant
from app.services import wishlist_services
from app.services.wishlist_services import WishlistService


def _product_with_variants(product_id: PydanticObjectId, skus: list[str]):
    variants = [ProductVariant(sku=sku, price=1000, discount_price=None, available_stock=5) for sku in skus]
    return SimpleNamespace(
        id=product_id,
        name="Phone X",
        brand="Acme",
        variants=variants,
        images=["/media/products/phone-x.jpg"],
    )


@pytest.mark.asyncio
async def test_add_item_inserts_wishlist_row_for_valid_product_and_sku(monkeypatch):
    user_id = PydanticObjectId()
    product_id = PydanticObjectId()
    insert_mock = AsyncMock()

    monkeypatch.setattr(
        wishlist_services.Product,
        "find_one",
        AsyncMock(return_value=_product_with_variants(product_id, ["PHX-01"])),
    )

    with patch("app.services.wishlist_services.Wishlist") as wishlist_cls:
        wishlist_cls.find.return_value.count = AsyncMock(return_value=0)
        wishlist_cls.return_value.insert = insert_mock
        await WishlistService.add_item(user_id, product_id, "PHX-01")

    insert_mock.assert_awaited_once()
    kwargs = wishlist_cls.call_args.kwargs
    assert kwargs["user_id"] == user_id
    assert kwargs["product_id"] == product_id
    assert kwargs["sku"] == "PHX-01"


@pytest.mark.asyncio
async def test_add_item_is_idempotent_on_duplicate_key(monkeypatch):
    user_id = PydanticObjectId()
    product_id = PydanticObjectId()
    insert_mock = AsyncMock(side_effect=DuplicateKeyError("duplicate"))

    monkeypatch.setattr(
        wishlist_services.Product,
        "find_one",
        AsyncMock(return_value=_product_with_variants(product_id, ["PHX-01"])),
    )

    with patch("app.services.wishlist_services.Wishlist") as wishlist_cls:
        wishlist_cls.find.return_value.count = AsyncMock(return_value=0)
        wishlist_cls.return_value.insert = insert_mock
        await WishlistService.add_item(user_id, product_id, "PHX-01")

    insert_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_item_raises_404_when_product_not_found(monkeypatch):
    monkeypatch.setattr(
        wishlist_services.Wishlist,
        "find",
        lambda _query: SimpleNamespace(count=AsyncMock(return_value=0)),
    )
    monkeypatch.setattr(wishlist_services.Product, "find_one", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await WishlistService.add_item(PydanticObjectId(), PydanticObjectId(), "PHX-01")

    assert exc_info.value.status_code == 404
    assert "product not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_add_item_raises_404_when_variant_not_found(monkeypatch):
    product_id = PydanticObjectId()
    monkeypatch.setattr(
        wishlist_services.Wishlist,
        "find",
        lambda _query: SimpleNamespace(count=AsyncMock(return_value=0)),
    )
    monkeypatch.setattr(
        wishlist_services.Product,
        "find_one",
        AsyncMock(return_value=_product_with_variants(product_id, ["PHX-01"])),
    )

    with pytest.raises(HTTPException) as exc_info:
        await WishlistService.add_item(PydanticObjectId(), product_id, "PHX-99")

    assert exc_info.value.status_code == 404
    assert "variant sku" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_add_item_rejects_when_wishlist_is_full(monkeypatch):
    find_one_mock = AsyncMock()
    monkeypatch.setattr(
        wishlist_services.Wishlist,
        "find",
        lambda _query: SimpleNamespace(count=AsyncMock(return_value=100)),
    )
    monkeypatch.setattr(wishlist_services.Product, "find_one", find_one_mock)

    with pytest.raises(DomainValidationError) as exc_info:
        await WishlistService.add_item(PydanticObjectId(), PydanticObjectId(), "PHX-01")

    assert "wishlist is full" in str(exc_info.value).lower()
    find_one_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_item_deletes_existing_row(monkeypatch):
    delete_mock = AsyncMock()
    row = SimpleNamespace(delete=delete_mock)

    monkeypatch.setattr(wishlist_services.Wishlist, "find_one", AsyncMock(return_value=row))

    await WishlistService.remove_item(PydanticObjectId(), PydanticObjectId(), "PHX-01")

    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_item_raises_404_when_row_missing(monkeypatch):
    monkeypatch.setattr(wishlist_services.Wishlist, "find_one", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await WishlistService.remove_item(PydanticObjectId(), PydanticObjectId(), "PHX-01")

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_get_user_wishlist_returns_empty_when_no_rows(monkeypatch):
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=[]))
    monkeypatch.setattr(wishlist_services.Wishlist, "find", lambda _query: cursor)

    result = await WishlistService.get_user_wishlist(PydanticObjectId())

    assert result == []


@pytest.mark.asyncio
async def test_get_user_wishlist_maps_rows_to_populated_response(monkeypatch):
    user_id = PydanticObjectId()
    product_id = PydanticObjectId()
    wishlist_id = PydanticObjectId()

    wishlist_rows = [SimpleNamespace(id=wishlist_id, user_id=user_id, product_id=product_id, sku="PHX-01")]
    wishlist_cursor = SimpleNamespace(to_list=AsyncMock(return_value=wishlist_rows))
    product_cursor = SimpleNamespace(to_list=AsyncMock(return_value=[_product_with_variants(product_id, ["PHX-01"])]))

    def _wishlist_find(query):
        if "user_id" in query:
            return wishlist_cursor
        return product_cursor

    monkeypatch.setattr(wishlist_services.Wishlist, "find", _wishlist_find)
    monkeypatch.setattr(wishlist_services.Product, "find", lambda _query: product_cursor)

    result = await WishlistService.get_user_wishlist(user_id)

    assert len(result) == 1
    assert str(result[0].wishlist_id) == str(wishlist_id)
    assert str(result[0].product_id) == str(product_id)
    assert result[0].sku == "PHX-01"
    assert result[0].price == 1000


@pytest.mark.asyncio
async def test_get_user_wishlist_skips_rows_with_missing_variant_or_product(monkeypatch):
    user_id = PydanticObjectId()
    live_product_id = PydanticObjectId()
    dead_product_id = PydanticObjectId()

    wishlist_rows = [
        SimpleNamespace(id=PydanticObjectId(), user_id=user_id, product_id=live_product_id, sku="PHX-01"),
        SimpleNamespace(id=PydanticObjectId(), user_id=user_id, product_id=dead_product_id, sku="OLD"),
        SimpleNamespace(id=PydanticObjectId(), user_id=user_id, product_id=live_product_id, sku="MISSING"),
    ]

    wishlist_cursor = SimpleNamespace(to_list=AsyncMock(return_value=wishlist_rows))
    product_cursor = SimpleNamespace(to_list=AsyncMock(return_value=[_product_with_variants(live_product_id, ["PHX-01"])]))

    monkeypatch.setattr(wishlist_services.Wishlist, "find", lambda _query: wishlist_cursor)
    monkeypatch.setattr(wishlist_services.Product, "find", lambda _query: product_cursor)

    result = await WishlistService.get_user_wishlist(user_id)

    assert len(result) == 1
    assert str(result[0].product_id) == str(live_product_id)
    assert result[0].sku == "PHX-01"


@pytest.mark.asyncio
async def test_remove_ghost_product_references_targets_product_or_variant(monkeypatch):
    delete_all_mock = AsyncMock()
    delete_sku_mock = AsyncMock()

    def _find(query):
        if "sku" in query:
            assert query["sku"] == "PHX-01"
            return SimpleNamespace(delete=delete_sku_mock)
        return SimpleNamespace(delete=delete_all_mock)

    monkeypatch.setattr(wishlist_services.Wishlist, "find", _find)

    product_id = PydanticObjectId()
    await WishlistService.remove_ghost_product_references(product_id)
    await WishlistService.remove_ghost_product_references(product_id, "PHX-01")

    delete_all_mock.assert_awaited_once()
    delete_sku_mock.assert_awaited_once()
