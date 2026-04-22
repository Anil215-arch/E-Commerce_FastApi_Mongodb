from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId

import app.main as main
from app.core.dependencies import get_current_user
from app.core.user_role import UserRole
from app.schemas.inventory_schema import InventoryVariantResponse


# cspell:ignore Bengaluru Karnataka


def _override_user(role: UserRole, user_id: PydanticObjectId | None = None):
    resolved_id = user_id or PydanticObjectId()

    async def _user():
        return SimpleNamespace(
            id=resolved_id,
            email="user@example.com",
            role=role,
            addresses=[],
        )

    return _user


def test_seller_can_get_variant_inventory_and_user_id_is_forwarded(client):
    seller_id = PydanticObjectId()
    product_id = PydanticObjectId()
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER, seller_id)

    service_response = InventoryVariantResponse(
        product_id=product_id,
        sku="SKU-INV-1",
        available_stock=12,
        reserved_stock=3,
        total_stock=15,
    )

    with patch(
        "app.api.api_v1.endpoints.seller.inventory.InventoryService.get_variant_inventory",
        new=AsyncMock(return_value=service_response),
    ) as mock_get_inventory:
        response = client.get(f"/api/v1/seller/inventory/products/{product_id}/variants/SKU-INV-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["sku"] == "SKU-INV-1"
    assert body["data"]["available_stock"] == 12
    assert body["data"]["reserved_stock"] == 3
    assert body["data"]["total_stock"] == 15

    await_args = mock_get_inventory.await_args
    assert await_args is not None
    called_args = await_args.args
    called_kwargs = await_args.kwargs
    assert str(called_args[0]) == str(product_id)
    assert called_args[1] == "SKU-INV-1"
    assert str(called_args[2]) == str(seller_id)


def test_seller_can_adjust_variant_inventory_and_payload_is_forwarded(client):
    seller_id = PydanticObjectId()
    product_id = PydanticObjectId()
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER, seller_id)

    service_response = InventoryVariantResponse(
        product_id=product_id,
        sku="SKU-INV-2",
        available_stock=20,
        reserved_stock=0,
        total_stock=20,
    )

    with patch(
        "app.api.api_v1.endpoints.seller.inventory.InventoryService.adjust_available_stock",
        new=AsyncMock(return_value=service_response),
    ) as mock_adjust_inventory:
        response = client.patch(
            f"/api/v1/seller/inventory/products/{product_id}/variants/SKU-INV-2",
            json={"request_id": "req-inv-00001", "delta": 5, "reason": "restock from supplier"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["available_stock"] == 20

    await_args = mock_adjust_inventory.await_args
    assert await_args is not None
    called_kwargs = await_args.kwargs
    assert str(called_kwargs["product_id"]) == str(product_id)
    assert called_kwargs["sku"] == "SKU-INV-2"
    assert str(called_kwargs["owner_seller_id"]) == str(seller_id)
    assert str(called_kwargs["actor_user_id"]) == str(seller_id)
    assert called_kwargs["request_id"] == "req-inv-00001"
    assert called_kwargs["delta"] == 5
    assert called_kwargs["reason"] == "restock from supplier"


def test_admin_inventory_read_disables_owner_enforcement(client):
    admin_id = PydanticObjectId()
    seller_id = PydanticObjectId()
    product_id = PydanticObjectId()
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.ADMIN, admin_id)

    service_response = InventoryVariantResponse(
        product_id=product_id,
        sku="SKU-INV-ADMIN",
        available_stock=7,
        reserved_stock=1,
        total_stock=8,
    )

    with patch(
        "app.api.api_v1.endpoints.seller.inventory.InventoryService.get_variant_inventory",
        new=AsyncMock(return_value=service_response),
    ) as mock_get_inventory:
        response = client.get(
            f"/api/v1/seller/inventory/products/{product_id}/variants/SKU-INV-ADMIN?seller_id={seller_id}"
        )

    assert response.status_code == 200
    await_args = mock_get_inventory.await_args
    assert await_args is not None
    called_args = await_args.args
    assert str(called_args[2]) == str(seller_id)


def test_admin_inventory_read_requires_seller_id(client):
    admin_id = PydanticObjectId()
    product_id = PydanticObjectId()
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.ADMIN, admin_id)

    response = client.get(f"/api/v1/seller/inventory/products/{product_id}/variants/SKU-INV-ADMIN")

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert "seller_id" in body["message"]


def test_customer_is_forbidden_from_inventory_management_routes(client):
    product_id = PydanticObjectId()
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.CUSTOMER)

    response = client.get(f"/api/v1/seller/inventory/products/{product_id}/variants/SKU-INV-3")

    assert response.status_code == 403
    body = response.json()
    assert body["status"] == "error"
    assert "permission" in body["message"].lower()


def test_adjust_inventory_rejects_invalid_increment_payload(client):
    product_id = PydanticObjectId()
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER)

    response = client.patch(
        f"/api/v1/seller/inventory/products/{product_id}/variants/SKU-INV-4",
        json={"request_id": "req-inv-00002", "delta": 0, "reason": "manual adjustment"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert "validation" in body["message"].lower()


def test_adjust_inventory_rejects_short_request_id_with_domain_error_shape(client):
    product_id = PydanticObjectId()
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER)

    response = client.patch(
        f"/api/v1/seller/inventory/products/{product_id}/variants/SKU-INV-4",
        json={"request_id": "short", "delta": 1, "reason": "manual adjustment"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    assert isinstance(body["data"], list)
