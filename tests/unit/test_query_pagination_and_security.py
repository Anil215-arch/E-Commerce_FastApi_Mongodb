from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId

from app.core.security import create_access_token, decode_token, get_password_hash, get_token_expiration, verify_password
from app.models.category_model import CategoryTranslation
from app.models.product_model import ProductTranslation
from app.models.product_variant_model import ProductVariant
from app.schemas.product_query_schema import ProductQueryParams, SortField, SortOrder
from app.services.product_query_services import ProductQueryService
from app.utils.pagination import CursorUtils
from app.utils.product_mapper import ProductMapper


class _FindChain:
    def __init__(self, result):
        self._result = result

    def sort(self, _):
        return self

    def limit(self, _):
        return self

    async def to_list(self):
        return self._result


class _AsyncMongoCursor:
    def __init__(self, result):
        self._result = result
        self.sort_calls = []
        self.skip_amount = None
        self.limit_amount = None

    def sort(self, field, direction):
        self.sort_calls.append((field, direction))
        return self

    def skip(self, amount):
        self.skip_amount = amount
        return self

    def limit(self, amount):
        self.limit_amount = amount
        return self

    async def to_list(self, length=None):
        self.length = length
        return self._result


class _CollectionStub:
    def __init__(self, cursor):
        self.cursor = cursor
        self.query = None

    def find(self, query):
        self.query = query
        return self.cursor


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


def test_product_query_search_defaults_created_at_sort_to_relevance():
    params = ProductQueryParams(search="   phone   ")

    assert params.search == "phone"
    assert params.sort_by == SortField.RELEVANCE


def test_product_query_rejects_relevance_sort_without_search():
    with pytest.raises(ValueError, match="Cannot sort by relevance"):
        ProductQueryParams(sort_by=SortField.RELEVANCE)


def test_product_query_rejects_offset_page_without_search():
    with pytest.raises(ValueError, match="Offset pagination"):
        ProductQueryParams(page=2)


def test_product_query_normalizes_brand_for_database_filtering():
    params = ProductQueryParams(brand="   acme labs   ")

    assert params.brand == "Acme Labs"


@pytest.mark.asyncio
async def test_list_products_search_uses_escaped_multilingual_native_collection_query():
    category_id = PydanticObjectId()
    raw_product = {"_id": PydanticObjectId(), "category_id": category_id}
    product = SimpleNamespace(id=raw_product["_id"], category_id=category_id)
    cursor = _AsyncMongoCursor([raw_product])
    collection = _CollectionStub(cursor)
    params = ProductQueryParams(search="कार.*", limit=10)

    with patch("app.services.product_query_services.Product.get_pymongo_collection", return_value=collection):
        with patch("app.services.product_query_services.Product.model_validate", return_value=product) as mock_validate:
            with patch("app.services.product_query_services.Category.find") as mock_category_find:
                mock_category_find.return_value.to_list = AsyncMock(return_value=[SimpleNamespace(id=category_id, name="Cars")])
                with patch("app.services.product_query_services.ProductMapper.serialize_product", return_value={"name": "कार"}):
                    data, next_cursor, has_next_page = await ProductQueryService.list_products(params, language="hi")

    assert data == [{"name": "कार"}]
    assert next_cursor is None
    assert has_next_page is False
    assert collection.query["$and"][0] == {"is_deleted": {"$ne": True}}
    search_or = collection.query["$and"][1]["$or"]
    assert {"translations.hi.name": {"$regex": r"कार\.\*", "$options": "i"}} in search_or
    assert {"translations.hi.description": {"$regex": r"कार\.\*", "$options": "i"}} in search_or
    assert {"variants.sku": {"$regex": r"कार\.\*", "$options": "i"}} in search_or
    expr_condition = next(condition["$expr"] for condition in search_or if "$expr" in condition)
    assert expr_condition["$or"][0]["$anyElementTrue"]["$map"]["input"] == {"$ifNull": ["$variants", []]}
    assert expr_condition["$or"][1]["$anyElementTrue"]["$map"]["input"] == {"$ifNull": ["$variants", []]}
    translated_attrs = (
        expr_condition["$or"][1]["$anyElementTrue"]["$map"]["in"]["$anyElementTrue"]["$map"]["input"]["$objectToArray"]["$ifNull"]
    )
    assert translated_attrs == ["$$variant.translations.hi.attributes", {}]
    assert (
        expr_condition["$or"][1]["$anyElementTrue"]["$map"]["in"]["$anyElementTrue"]["$map"]["in"]["$regexMatch"]["regex"]
        == r"कार\.\*"
    )
    assert cursor.skip_amount == 0
    assert cursor.limit_amount == params.limit + 1
    mock_validate.assert_called_once_with(raw_product)


@pytest.mark.asyncio
async def test_list_products_search_marks_next_page_when_native_cursor_returns_extra_record():
    category_id = PydanticObjectId()
    raw_products = [
        {"_id": PydanticObjectId(), "category_id": category_id},
        {"_id": PydanticObjectId(), "category_id": category_id},
    ]
    products = [
        SimpleNamespace(id=raw_products[0]["_id"], category_id=category_id),
        SimpleNamespace(id=raw_products[1]["_id"], category_id=category_id),
    ]
    cursor = _AsyncMongoCursor(raw_products)
    collection = _CollectionStub(cursor)
    params = ProductQueryParams(search="phone", limit=1)

    with patch("app.services.product_query_services.Product.get_pymongo_collection", return_value=collection):
        with patch("app.services.product_query_services.Product.model_validate", side_effect=products):
            with patch("app.services.product_query_services.Category.find") as mock_category_find:
                mock_category_find.return_value.to_list = AsyncMock(return_value=[SimpleNamespace(id=category_id, name="Phones")])
                with patch("app.services.product_query_services.ProductMapper.serialize_product", return_value={"ok": True}):
                    data, next_cursor, has_next_page = await ProductQueryService.list_products(params)

    assert data == [{"ok": True}]
    assert next_cursor is None
    assert has_next_page is True


def test_product_mapper_localizes_product_and_category_with_base_fallback_for_missing_translation():
    category = SimpleNamespace(
        id=PydanticObjectId(),
        name="Car Accessories",
        translations={"hi": CategoryTranslation(name="कार एक्सेसरीज़")},
    )
    product = SimpleNamespace(
        id=PydanticObjectId(),
        name="Car Mat",
        description="Durable all weather car mat",
        brand="3M",
        category_id=category.id,
        translations={"hi": ProductTranslation(name="कार मैट", description="टिकाऊ कार मैट विवरण")},
        variants=[
            ProductVariant(
                sku="MAT-001",
                price=1000,
                discount_price=900,
                available_stock=5,
                reserved_stock=0,
                attributes={"finish": "Matte"},
            )
        ],
        price=900,
        images=[],
        average_rating=0.0,
        num_reviews=0,
        rating_sum=0,
        rating_breakdown={"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        specifications={},
        is_available=True,
        is_featured=False,
    )

    localized = ProductMapper.serialize_product(product, category, language="hi")
    fallback = ProductMapper.serialize_product(product, category, language="ja")

    assert localized.name == "कार मैट"
    assert localized.category.name == "कार एक्सेसरीज़"
    assert localized.variants[0].attributes == {"finish": "Matte"}
    assert fallback.name == "Car Mat"
    assert fallback.description == "Durable all weather car mat"
    assert fallback.category.name == "Car Accessories"


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
