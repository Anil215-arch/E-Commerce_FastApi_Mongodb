from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId

import app.main as main
from app.core.exceptions import DomainValidationError
from app.core.dependencies import get_current_user
from app.core.user_role import UserRole


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
                "available_stock": 5,
                "reserved_stock": 0,
                "attributes": {},
            }
        ],
        "price": 45000,
        "images": [],
        "average_rating": 4.2,
        "num_reviews": 10,
        "rating_sum": 42,
        "rating_breakdown": {"1": 0, "2": 0, "3": 1, "4": 5, "5": 4},
        "specifications": {},
        "is_available": True,
        "is_featured": False,
    }

    with patch(
        "app.api.api_v1.endpoints.public.products.ProductQueryService.list_products",
        new=AsyncMock(return_value=([product_payload], "cursor-1", False)),
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

    response = client.get("/api/v1/customer/cart/")

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
    response = client.post("/api/v1/customer/cart/items", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    assert isinstance(body["data"], list)


def test_add_cart_item_rejects_quantity_above_limit_with_standard_error_shape(client):
    async def _user_with_id():
        return SimpleNamespace(id=PydanticObjectId())

    main.app.dependency_overrides[get_current_user] = _user_with_id

    payload = {
        "product_id": str(PydanticObjectId()),
        "sku": "SKU-1",
        "quantity": 11,
    }
    response = client.post("/api/v1/customer/cart/items", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    assert isinstance(body["data"], list)


def test_add_cart_item_rejects_invalid_sku_pattern_with_standard_error_shape(client):
    async def _user_with_id():
        return SimpleNamespace(id=PydanticObjectId())

    main.app.dependency_overrides[get_current_user] = _user_with_id

    payload = {
        "product_id": str(PydanticObjectId()),
        "sku": "BAD SKU!*",
        "quantity": 1,
    }
    response = client.post("/api/v1/customer/cart/items", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    assert isinstance(body["data"], list)


def test_order_checkout_rejects_whitespace_batch_id_with_standard_error_shape(client):
    async def _user_with_id():
        return SimpleNamespace(id=PydanticObjectId(), role=UserRole.CUSTOMER)

    main.app.dependency_overrides[get_current_user] = _user_with_id

    with patch(
        "app.services.order_services.User.get",
        new=AsyncMock(return_value=SimpleNamespace(addresses=[SimpleNamespace()])),
    ):
        response = client.post(
            "/api/v1/customer/orders/checkout",
            json={
                "checkout_batch_id": "        ",
                "shipping_address_index": 0,
                "billing_address_index": 0,
                "payment_method": "CARD",
            },
        )

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Domain validation failed"
    assert "checkout_batch_id cannot be empty" in body["data"].lower()


def test_order_cancel_rejects_whitespace_reason_with_standard_error_shape(client):
    async def _user_with_id():
        return SimpleNamespace(id=PydanticObjectId(), role=UserRole.CUSTOMER)

    main.app.dependency_overrides[get_current_user] = _user_with_id

    response = client.patch(
        f"/api/v1/customer/orders/{PydanticObjectId()}/cancel",
        json={"reason": "          "},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Domain validation failed"
    assert "cannot be empty" in body["data"].lower()


def test_unread_notification_count_returns_success_envelope(client):
    async def _user_with_id():
        return SimpleNamespace(id=PydanticObjectId())

    main.app.dependency_overrides[get_current_user] = _user_with_id

    with patch(
        "app.api.api_v1.endpoints.customer.notifications.NotificationService.get_unread_count",
        new=AsyncMock(return_value=7),
    ):
        response = client.get("/api/v1/customer/notifications/unread-count")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message"] == "Unread notification count fetched successfully"
    assert body["data"]["unread_count"] == 7


def test_unread_notification_count_returns_401_when_user_id_missing(client):
    async def _user_without_id():
        return SimpleNamespace(id=None)

    main.app.dependency_overrides[get_current_user] = _user_without_id

    response = client.get("/api/v1/customer/notifications/unread-count")

    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"
    assert "missing" in body["message"].lower()


def test_review_create_maps_domain_validation_error_to_400(client):
    async def _user_with_id():
        return SimpleNamespace(id=PydanticObjectId(), role=UserRole.CUSTOMER)

    main.app.dependency_overrides[get_current_user] = _user_with_id

    with patch(
        "app.api.api_v1.endpoints.customer.reviews.ReviewService.create_review",
        new=AsyncMock(side_effect=DomainValidationError("Review text is too short.")),
    ):
        response = client.post(
            f"/api/v1/customer/reviews/products/{PydanticObjectId()}",
            json={"rating": 5, "review": "great", "images": []},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Domain validation failed"
    assert "too short" in body["data"].lower()


def test_wishlist_add_maps_domain_validation_error_to_400(client):
    async def _user_with_id():
        return SimpleNamespace(id=PydanticObjectId())

    main.app.dependency_overrides[get_current_user] = _user_with_id

    with patch(
        "app.api.api_v1.endpoints.wishlist_api.WishlistService.add_item",
        new=AsyncMock(side_effect=DomainValidationError("Wishlist is full.")),
    ):
        response = client.post(
            "/api/v1/customers/wishlist/",
            json={"product_id": str(PydanticObjectId()), "sku": "PHX-01"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Domain validation failed"
    assert "wishlist is full" in body["data"].lower()
