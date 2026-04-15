from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId

import main
from app.core.dependencies import get_current_user


def test_products_list_returns_paginated_items_without_double_data(client):
    product_payload = {
        "_id": str(PydanticObjectId()),
        "name": "Phone",
        "description": "Latest smartphone model with flagship hardware",
        "brand": "Acme",
        "category": {"_id": str(PydanticObjectId()), "name": "Electronics"},
        "variants": [
            {
                "sku": "PHN-001",
                "price": 50000,
                "discount_price": 45000,
                "stock": 5,
                "attributes": {},
            }
        ],
        "price": 45000,
        "images": [],
        "rating": 4.2,
        "num_reviews": 10,
        "specifications": {},
        "is_available": True,
        "is_featured": False,
    }

    with patch(
        "app.api.api_v1.endpoints.product_api.ProductQueryService.list_products",
        new=AsyncMock(return_value=([product_payload], "cursor-1")),
    ):
        response = client.get("/api/v1/products/?limit=10&sort_by=created_at&sort_order=desc")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "data" in body
    assert "items" in body["data"]
    assert "data" not in body["data"]
    assert body["data"]["meta"]["next_cursor"] == "cursor-1"
    assert body["data"]["items"][0]["name"] == "Phone"


def test_products_list_bad_price_range_returns_422_validation_envelope(client):
    response = client.get("/api/v1/products/?min_price=100&max_price=50")

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    assert isinstance(body["data"], list)


def test_cart_endpoint_returns_401_when_authenticated_user_id_is_missing(client):
    async def _user_without_id():
        return SimpleNamespace(id=None)

    main.app.dependency_overrides[get_current_user] = _user_without_id

    response = client.get("/api/v1/cart/")

    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"
    assert "missing" in body["message"].lower()


def test_add_cart_item_rejects_invalid_quantity_with_standard_error_shape(client):
    async def _user_with_id():
        return SimpleNamespace(id=PydanticObjectId())

    main.app.dependency_overrides[get_current_user] = _user_with_id

    payload = {
        "product_id": str(PydanticObjectId()),
        "sku": "SKU-1",
        "quantity": 0,
    }
    response = client.post("/api/v1/cart/items", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    assert isinstance(body["data"], list)
