from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId
from fastapi import HTTPException

import app.main as main
from app.core.dependencies import get_current_user


def _override_current_user(user_id: PydanticObjectId | None = None):
    resolved_id = user_id or PydanticObjectId()

    async def _current_user():
        return SimpleNamespace(
            id=resolved_id,
            email="john@example.com",
            user_name="john",
            role="customer",
            addresses=[],
        )

    return _current_user


def _wishlist_populated_item() -> dict:
    return {
        "_id": str(PydanticObjectId()),
        "product_id": str(PydanticObjectId()),
        "name": "Phone X",
        "brand": "Acme",
        "sku": "PHX-01",
        "price": 9000,
        "image": "/media/products/phone-x.jpg",
    }


def test_add_to_wishlist_route_returns_201_success(client):
    user_id = PydanticObjectId()
    product_id = str(PydanticObjectId())
    main.app.dependency_overrides[get_current_user] = _override_current_user(user_id)

    with patch(
        "app.api.api_v1.endpoints.wishlist_api.WishlistService.add_item",
        new=AsyncMock(return_value=None),
    ) as mock_add:
        response = client.post(
            "/api/v1/wishlist/",
            json={"product_id": product_id, "sku": "PHX-01"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert "added" in body["message"].lower()

    await_args = mock_add.await_args
    assert await_args is not None
    assert str(await_args.args[0]) == str(user_id)
    assert str(await_args.args[1]) == product_id
    assert await_args.args[2] == "PHX-01"


def test_add_to_wishlist_route_returns_422_for_missing_sku(client):
    main.app.dependency_overrides[get_current_user] = _override_current_user()

    with patch(
        "app.api.api_v1.endpoints.wishlist_api.WishlistService.add_item",
        new=AsyncMock(),
    ) as mock_add:
        response = client.post(
            "/api/v1/wishlist/",
            json={"product_id": str(PydanticObjectId())},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    mock_add.assert_not_awaited()


def test_add_to_wishlist_route_maps_service_404(client):
    main.app.dependency_overrides[get_current_user] = _override_current_user()

    with patch(
        "app.api.api_v1.endpoints.wishlist_api.WishlistService.add_item",
        new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Product not found or unavailable.")),
    ):
        response = client.post(
            "/api/v1/wishlist/",
            json={"product_id": str(PydanticObjectId()), "sku": "PHX-01"},
        )

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert "not found" in body["message"].lower()


def test_remove_from_wishlist_route_returns_success(client):
    user_id = PydanticObjectId()
    product_id = str(PydanticObjectId())
    main.app.dependency_overrides[get_current_user] = _override_current_user(user_id)

    with patch(
        "app.api.api_v1.endpoints.wishlist_api.WishlistService.remove_item",
        new=AsyncMock(return_value=None),
    ) as mock_remove:
        response = client.delete(f"/api/v1/wishlist/{product_id}/variants/PHX-01")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "removed" in body["message"].lower()

    await_args = mock_remove.await_args
    assert await_args is not None
    assert str(await_args.args[0]) == str(user_id)
    assert str(await_args.args[1]) == product_id
    assert await_args.args[2] == "PHX-01"


def test_remove_from_wishlist_route_returns_422_for_invalid_product_id(client):
    main.app.dependency_overrides[get_current_user] = _override_current_user()

    with patch(
        "app.api.api_v1.endpoints.wishlist_api.WishlistService.remove_item",
        new=AsyncMock(),
    ) as mock_remove:
        response = client.delete("/api/v1/wishlist/not-an-objectid/variants/PHX-01")

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    mock_remove.assert_not_awaited()


def test_get_wishlist_route_returns_items(client):
    main.app.dependency_overrides[get_current_user] = _override_current_user()

    with patch(
        "app.api.api_v1.endpoints.wishlist_api.WishlistService.get_user_wishlist",
        new=AsyncMock(return_value=[_wishlist_populated_item()]),
    ) as mock_get:
        response = client.get("/api/v1/wishlist/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "wishlist fetched" in body["message"].lower()
    assert len(body["data"]) == 1
    assert body["data"][0]["sku"] == "PHX-01"
    mock_get.assert_awaited_once()


def test_get_wishlist_route_returns_empty_list(client):
    main.app.dependency_overrides[get_current_user] = _override_current_user()

    with patch(
        "app.api.api_v1.endpoints.wishlist_api.WishlistService.get_user_wishlist",
        new=AsyncMock(return_value=[]),
    ):
        response = client.get("/api/v1/wishlist/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"] == []
