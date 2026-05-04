from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId

import app.main as main
from app.core.dependencies import get_bearer_token, get_current_user
from app.core.user_role import UserRole

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


def _valid_product_create_payload() -> dict:
    return {
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
                "attributes": {},
            }
        ],
        "specifications": {},
        "is_available": True,
        "is_featured": False,
    }


def test_openapi_has_namespaced_groups_and_blind_spot_routes(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    doc = response.json()
    paths: dict = doc["paths"]

    tags = {
        operation_tag
        for item in paths.values()
        for op in item.values()
        for operation_tag in op.get("tags", [])
    }

    assert "Users" in tags
    assert "Products" in tags
    assert "Reviews" in tags

    assert "/api/v1/reviews/products/{product_id}" in paths
    assert "post" in paths["/api/v1/reviews/products/{product_id}"]

    assert "/api/v1/reviews/products/{product_id}/reviews" in paths
    assert "get" in paths["/api/v1/reviews/products/{product_id}/reviews"]


def test_openapi_contract_has_order_namespace(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths: dict = response.json()["paths"]

    assert any(path.startswith("/api/v1/orders") for path in paths), (
        "Missing order routes in namespaced gateway"
    )


def test_customer_is_forbidden_from_seller_inventory_routes(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.CUSTOMER)

    response = client.post("/api/v1/products/", json=_valid_product_create_payload())

    assert response.status_code == 403
    body = response.json()
    assert body["status"] == "error"
    assert "permission" in body["message"].lower()


def test_seller_is_forbidden_from_admin_user_routes(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER)

    response = client.get("/api/v1/users/")

    assert response.status_code == 403
    body = response.json()
    assert body["status"] == "error"
    assert "permission" in body["message"].lower()


def test_seller_product_create_forwards_user_id_to_service(client):
    seller_id = PydanticObjectId()
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER, seller_id)

    product_response = {
        "_id": str(PydanticObjectId()),
        "name": "Phone X",
        "description": "Modern smartphone with long battery and strong camera",
        "brand": "Acme",
        "category": {"_id": str(PydanticObjectId()), "name": "Electronics"},
        "variants": [
            {
                "sku": "PHX-01",
                "price": 10000,
                "discount_price": 9000,
                "available_stock": 5,
                "reserved_stock": 0,
                "attributes": {},
            }
        ],
        "price": 9000,
        "images": [],
        "average_rating": 0.0,
        "num_reviews": 0,
        "rating_sum": 0,
        "rating_breakdown": {},
        "specifications": {},
        "is_available": True,
        "is_featured": False,
    }

    with patch(
        "app.api.api_v1.endpoints.product_api.ProductService.create_product",
        new=AsyncMock(return_value=product_response),
    ) as mock_create:
        response = client.post("/api/v1/products/", json=_valid_product_create_payload())

    assert response.status_code == 201
    await_args = mock_create.await_args
    assert await_args is not None
    called_args = await_args.args
    assert str(called_args[1]) == str(seller_id)


def test_namespaced_core_loop_smoke_with_service_stubs(client):
    register_response = {
        "_id": str(PydanticObjectId()),
        "user_name": "john",
        "email": "john@example.com",
        "mobile": "9876543210",
        "role": "customer",
        "is_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    login_response = {
        "access_token": "access.token",
        "refresh_token": "refresh.token",
        "token_type": "bearer",
    }

    checkout_response = {
        "checkout_batch_id": "batch-1",
        "transaction_id": str(PydanticObjectId()),
        "amount": 9000,
        "transaction_status": "SUCCESS",
        "payment_method": "CARD",
        "orders": [
            {
                "_id": str(PydanticObjectId()),
                "user_id": str(PydanticObjectId()),
                "seller_id": str(PydanticObjectId()),
                "checkout_batch_id": "batch-1",
                "transaction_id": str(PydanticObjectId()),
                "items": [
                    {
                        "product_id": str(PydanticObjectId()),
                        "seller_id": str(PydanticObjectId()),
                        "sku": "PHX-01",
                        "product_name": "Phone X",
                        "quantity": 1,
                        "purchase_price": 9000,
                    }
                ],
                "shipping_address": {
                    "full_name": "John Doe",
                    "phone_number": "9876543210",
                    "street_address": "123 Main Street",
                    "city": "Bengaluru",
                    "postal_code": "560001",
                    "state": "Karnataka",
                    "country": "India",
                },
                "billing_address": {
                    "full_name": "John Doe",
                    "phone_number": "9876543210",
                    "street_address": "123 Main Street",
                    "city": "Bengaluru",
                    "postal_code": "560001",
                    "state": "Karnataka",
                    "country": "India",
                },
                "subtotal": 9000,
                "tax_amount": 0,
                "shipping_fee": 0,
                "grand_total": 9000,
                "status": "PENDING",
                "payment_status": "PAID",
                "refunded_amount": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }
    order_id = checkout_response["orders"][0]["_id"]

    invoice_response = SimpleNamespace(invoice_number="INV-1001")

    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.CUSTOMER)

    address_payload = {
        "full_name": "John Doe",
        "phone_number": "9876543210",
        "street_address": "123 Main Street",
        "city": "Bengaluru",
        "postal_code": "560001",
        "state": "Karnataka",
        "country": "India",
    }

    with patch(
        "app.api.api_v1.endpoints.auth_api.UserServices.user_registration",
        new=AsyncMock(return_value=register_response),
    ), patch(
        "app.api.api_v1.endpoints.auth_api.UserServices.login_and_issue_tokens",
        new=AsyncMock(return_value=login_response),
    ), patch(
        "app.api.api_v1.endpoints.cart_api.CartService.add_to_cart",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.api.api_v1.endpoints.order_api.OrderService.checkout",
        new=AsyncMock(return_value=checkout_response),
    ), patch(
        "app.api.api_v1.endpoints.order_api.InvoiceService.get_invoice_by_order_id",
        new=AsyncMock(return_value=invoice_response),
    ), patch(
        "app.api.api_v1.endpoints.order_api.PDFService.generate_invoice_pdf",
        return_value=b"%PDF-1.4 test pdf",
    ), patch(
        "app.api.api_v1.endpoints.product_api.ProductQueryService.list_products",
        new=AsyncMock(
            return_value=(
                [
                    {
                        "_id": str(PydanticObjectId()),
                        "name": "Phone X",
                        "description": "Modern smartphone with long battery and strong camera",
                        "brand": "Acme",
                        "category": {"_id": str(PydanticObjectId()), "name": "Electronics"},
                        "variants": [
                            {
                                "sku": "PHX-01",
                                "price": 10000,
                                "discount_price": 9000,
                                "available_stock": 5,
                                "reserved_stock": 0,
                                "attributes": {},
                            }
                        ],
                        "price": 9000,
                        "images": [],
                        "average_rating": 0.0,
                        "num_reviews": 0,
                        "rating_sum": 0,
                        "rating_breakdown": {},
                        "specifications": {},
                        "is_available": True,
                        "is_featured": False,
                    }
                ],
                "cursor-1",
                False,
            )
        ),
    ):
        register = client.post(
            "/api/v1/auth/register",
            json={
                "user_name": "john",
                "email": "john@example.com",
                "password": "StrongPass123!",
                "mobile": "9876543210",
            },
        )
        assert register.status_code == 201

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "john@example.com", "password": "StrongPass123!"},
        )
        assert login.status_code == 200

        product_list = client.get("/api/v1/products/?limit=1")
        assert product_list.status_code == 200
        product_data = product_list.json()["data"]["items"][0]
        product_id = product_data.get("_id") or product_data.get("id")

        add_cart = client.post(
            "/api/v1/cart/items",
            json={
                "product_id": product_id,
                "sku": product_data["variants"][0]["sku"],
                "quantity": 1,
            },
        )
        assert add_cart.status_code == 200

        checkout = client.post(
            "/api/v1/orders/checkout",
            json={
                "checkout_batch_id": "gateway-smoke-batch-001",
                "shipping_address_index": 0,
                "billing_address_index": 0,
                "payment_method": "CARD",
            },
        )
        assert checkout.status_code == 201

        downloaded_order = checkout.json()["data"]["orders"][0]
        downloaded_order_id = downloaded_order.get("_id") or downloaded_order.get("id")
        pdf_response = client.get(f"/api/v1/orders/{downloaded_order_id}/invoice/pdf")
        assert pdf_response.status_code == 200
        assert "application/pdf" in (pdf_response.headers.get("content-type") or "")
