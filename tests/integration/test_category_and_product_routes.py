from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId

import app.main as main
from app.core.dependencies import get_current_user
from app.core.user_role import UserRole


def test_category_create_maps_service_error_to_400(client):
    async def _admin_user():
        return SimpleNamespace(id=PydanticObjectId(), role=UserRole.ADMIN)

    main.app.dependency_overrides[get_current_user] = _admin_user

    with patch(
        "app.api.api_v1.endpoints.admin.categories.CategoryService.create_category",
        new=AsyncMock(return_value=(None, "Parent category not found.")),
    ):
        response = client.post("/api/v1/admin/categories/", json={"name": "Phones", "parent_id": str(PydanticObjectId())})

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert "parent category not found" in body["message"].lower()


def test_category_tree_route_returns_nested_payload(client):
    tree_payload = [
        {
            "_id": str(PydanticObjectId()),
            "name": "Root",
            "parent_id": None,
            "children": [],
        }
    ]

    with patch("app.api.api_v1.endpoints.public.categories.CategoryService.get_category_tree", new=AsyncMock(return_value=tree_payload)):
        response = client.get("/api/v1/categories/tree")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert isinstance(body["data"], list)
    assert body["data"][0]["name"] == "Root"


def test_product_create_requires_admin_or_seller_role(client):
    async def _customer_user():
        return SimpleNamespace(id=PydanticObjectId(), role=UserRole.CUSTOMER)

    main.app.dependency_overrides[get_current_user] = _customer_user

    response = client.post(
        "/api/v1/seller/products/",
        json={
            "name": "Phone X",
            "description": "Modern smartphone with long battery and strong camera",
            "brand": "Acme",
            "category_id": str(PydanticObjectId()),
            "variants": [
                {
                    "sku": "PHX-01",
                    "price": 10000,
                    "discount_price": 9000,
                    "available_stock": 5,
                    "reserved_stock": 0,
                    "attributes": {}
                }
            ],
            "rating": 4.5,
            "num_reviews": 0,
            "specifications": {},
            "is_available": True,
            "is_featured": False,
        },
    )

    assert response.status_code == 403
    body = response.json()
    assert body["status"] == "error"
    assert "permission" in body["message"].lower()


def test_product_read_one_returns_404_when_not_found(client):
    with patch("app.api.api_v1.endpoints.public.products.ProductQueryService.get_product", new=AsyncMock(return_value=None)):
        response = client.get(f"/api/v1/products/{PydanticObjectId()}")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Product not found"


def test_product_delete_maps_false_service_result_to_404(client):
    async def _admin_user():
        return SimpleNamespace(id=PydanticObjectId(), role=UserRole.ADMIN)

    main.app.dependency_overrides[get_current_user] = _admin_user

    with patch("app.api.api_v1.endpoints.admin.products.ProductService.delete_product", new=AsyncMock(return_value=False)):
        response = client.delete(f"/api/v1/admin/products/{PydanticObjectId()}")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Product not found"


def test_category_list_route_success_shape(client):
    categories = [
        {"_id": str(PydanticObjectId()), "name": "Electronics", "parent_id": None},
        {"_id": str(PydanticObjectId()), "name": "Laptops", "parent_id": str(PydanticObjectId())},
    ]

    with patch("app.api.api_v1.endpoints.public.categories.CategoryService.get_all_categories", new=AsyncMock(return_value=categories)):
        response = client.get("/api/v1/categories/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert len(body["data"]) == 2
