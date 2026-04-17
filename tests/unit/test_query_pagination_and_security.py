from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId

from app.core.security import create_access_token, decode_token, get_password_hash, get_token_expiration, verify_password
from app.schemas.product_query_schema import ProductQueryParams, SortField, SortOrder
from app.services.product_query_services import ProductQueryService
from app.utils.pagination import CursorUtils


class _FindChain:
    def __init__(self, result):
        self._result = result

    def sort(self, _):
        return self

    def limit(self, _):
        return self

    async def to_list(self):
        return self._result


def test_decode_cursor_invalid_payload_returns_none():
    assert CursorUtils.decode_cursor("###broken###") is None


def test_token_roundtrip_and_password_hash_roundtrip():
    token = create_access_token({"sub": "user@example.com"}, expires_delta=timedelta(minutes=5))
    payload = decode_token(token)
    assert payload["token_type"] == "access"
    assert payload["sub"] == "user@example.com"

    hashed = get_password_hash("StrongPass123!")
    assert verify_password("StrongPass123!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_get_token_expiration_without_exp_claim_raises_value_error():
    with pytest.raises(ValueError):
        get_token_expiration({"sub": "x"})


@pytest.mark.asyncio
async def test_list_products_ignores_invalid_cursor_and_returns_first_page():
    category_id = PydanticObjectId()
    product = SimpleNamespace(id=PydanticObjectId(), category_id=category_id)
    params = ProductQueryParams(limit=10, cursor="not-base64", sort_by=SortField.CREATED_AT, sort_order=SortOrder.DESC)

    with patch("app.services.product_query_services.Product.find", return_value=_FindChain([product])):
        with patch("app.services.product_query_services.Category.find") as mock_category_find:
            mock_category_find.return_value.to_list = AsyncMock(return_value=[SimpleNamespace(id=category_id, name="Cat")])
            with patch("app.services.product_query_services.ProductMapper.serialize_product", return_value={"ok": True}) as mock_map:
                data, next_cursor, has_next_page = await ProductQueryService.list_products(params)

    assert next_cursor is None
    assert has_next_page is False
    assert data == [{"ok": True}]
    mock_map.assert_called_once()


@pytest.mark.asyncio
async def test_list_products_generates_next_cursor_when_extra_record_exists():
    category_id = PydanticObjectId()
    p1 = SimpleNamespace(id=PydanticObjectId(), category_id=category_id, price=100)
    p2 = SimpleNamespace(id=PydanticObjectId(), category_id=category_id, price=110)
    p3 = SimpleNamespace(id=PydanticObjectId(), category_id=category_id, price=120)
    params = ProductQueryParams(limit=2, sort_by=SortField.PRICE, sort_order=SortOrder.ASC)

    with patch("app.services.product_query_services.Product.find", return_value=_FindChain([p1, p2, p3])):
        with patch("app.services.product_query_services.Category.find") as mock_category_find:
            mock_category_find.return_value.to_list = AsyncMock(return_value=[SimpleNamespace(id=category_id, name="Cat")])
            with patch("app.services.product_query_services.ProductMapper.serialize_product", side_effect=[{"id": 1}, {"id": 2}]):
                data, next_cursor, has_next_page = await ProductQueryService.list_products(params)

    assert len(data) == 2
    assert next_cursor is not None
    assert has_next_page is True
    decoded = CursorUtils.decode_cursor(next_cursor)
    assert decoded is not None
    assert "id" in decoded
    assert decoded["v"] == 110


@pytest.mark.asyncio
async def test_get_product_returns_none_when_missing():
    with patch("app.services.product_query_services.Product.get", new=AsyncMock(return_value=None)):
        assert await ProductQueryService.get_product(PydanticObjectId()) is None


@pytest.mark.asyncio
async def test_get_product_returns_serialized_payload_when_found():
    category_id = PydanticObjectId()
    product = SimpleNamespace(id=PydanticObjectId(), category_id=category_id)
    category = SimpleNamespace(id=category_id, name="Cat")

    with patch("app.services.product_query_services.Product.get", new=AsyncMock(return_value=product)):
        with patch("app.services.product_query_services.Category.get", new=AsyncMock(return_value=category)):
            with patch("app.services.product_query_services.ProductMapper.serialize_product", return_value={"id": "x"}):
                payload = await ProductQueryService.get_product(PydanticObjectId())

    assert payload == {"id": "x"}
