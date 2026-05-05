from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from fastapi import Request

import app.main as main
from app.core.dependencies import get_bearer_token, get_current_user
from app.core.i18n import t
from app.core.message_keys import Msg
from app.core.user_role import UserRole


ENDPOINTS_DIR = Path("app/api/api_v1/endpoints")


def _message(key: str, language: str = "en") -> str:
    return t(cast(Request, object()), key, language=language)


def _current_user(
    *,
    role: UserRole = UserRole.CUSTOMER,
    preferred_language: str | None = None,
    user_id: PydanticObjectId | None = None,
):
    resolved_id = user_id or PydanticObjectId()

    async def _user():
        return SimpleNamespace(
            id=resolved_id,
            user_name="john",
            email="john@example.com",
            mobile="9876543210",
            role=role,
            is_verified=True,
            preferred_language=preferred_language,
            addresses=[],
            created_at=datetime.now(timezone.utc),
        )

    return _user


def _user_payload(user_id: PydanticObjectId | None = None) -> dict[str, Any]:
    return {
        "_id": str(user_id or PydanticObjectId()),
        "user_name": "john",
        "email": "john@example.com",
        "mobile": "9876543210",
        "role": "customer",
        "is_verified": True,
        "preferred_language": "en",
        "addresses": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _review_payload(review_text: str = "Original user text") -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "_id": str(PydanticObjectId()),
        "product_id": str(PydanticObjectId()),
        "user_id": str(PydanticObjectId()),
        "rating": 5,
        "review": review_text,
        "images": [],
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.parametrize(
    ("patch_target", "path", "payload", "service_return", "message_key"),
    [
        (
            "app.api.api_v1.endpoints.auth_api.UserServices.user_registration",
            "/api/v1/auth/register",
            {
                "user_name": "john",
                "email": "john@example.com",
                "password": "StrongPass123!",
                "mobile": "9876543210",
            },
            _user_payload(),
            Msg.USER_REGISTERED_SUCCESSFULLY,
        ),
        (
            "app.api.api_v1.endpoints.auth_api.UserServices.login_and_issue_tokens",
            "/api/v1/auth/login",
            {"email": "john@example.com", "password": "StrongPass123!"},
            {"access_token": "access", "refresh_token": "refresh", "token_type": "bearer"},
            Msg.USER_LOGGED_IN_SUCCESSFULLY,
        ),
        (
            "app.api.api_v1.endpoints.auth_api.UserServices.refresh_user_token",
            "/api/v1/auth/refresh",
            {"refresh_token": "refresh"},
            {"access_token": "access", "refresh_token": "refresh2", "token_type": "bearer"},
            Msg.TOKEN_REFRESHED_SUCCESSFULLY,
        ),
        (
            "app.api.api_v1.endpoints.auth_api.UserServices.verify_email_registration",
            "/api/v1/auth/verify-registration",
            {"email": "john@example.com", "otp_code": "123456"},
            Msg.EMAIL_VERIFIED_SUCCESSFULLY,
            Msg.EMAIL_VERIFIED_SUCCESSFULLY,
        ),
        (
            "app.api.api_v1.endpoints.auth_api.UserServices.resend_verification_otp",
            "/api/v1/auth/resend-otp",
            {"email": "john@example.com"},
            None,
            Msg.OTP_SENT_SUCCESSFULLY,
        ),
        (
            "app.api.api_v1.endpoints.auth_api.UserServices.forgot_password_request",
            "/api/v1/auth/forgot-password",
            {"email": "john@example.com"},
            None,
            Msg.PASSWORD_RESET_CODE_SENT,
        ),
        (
            "app.api.api_v1.endpoints.auth_api.UserServices.reset_password_with_otp",
            "/api/v1/auth/reset-password",
            {"email": "john@example.com", "otp_code": "123456", "new_password": "StrongPass123!"},
            None,
            Msg.PASSWORD_RESET_SUCCESSFULLY,
        ),
    ],
)
def test_public_auth_routes_use_accept_language(
    client,
    patch_target: str,
    path: str,
    payload: dict[str, Any],
    service_return: Any,
    message_key: str,
):
    with patch(patch_target, new=AsyncMock(return_value=service_return)):
        response = client.post(path, json=payload, headers={"Accept-Language": "ja"})

    assert response.status_code in {200, 201}
    assert response.json()["message"] == _message(message_key, "ja")


@pytest.mark.parametrize(
    ("headers", "expected_language"),
    [
        ({"Accept-Language": "hi"}, "hi"),
        ({"Accept-Language": "ja"}, "ja"),
        ({}, "en"),
        ({"Accept-Language": "fr, es;q=0.9"}, "en"),
    ],
)
def test_public_auth_routes_fallback_by_accept_language(client, headers: dict[str, str], expected_language: str):
    with patch(
        "app.api.api_v1.endpoints.auth_api.UserServices.refresh_user_token",
        new=AsyncMock(return_value={"access_token": "access", "refresh_token": "refresh", "token_type": "bearer"}),
    ):
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "refresh"},
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["message"] == _message(Msg.TOKEN_REFRESHED_SUCCESSFULLY, expected_language)


@pytest.mark.parametrize(
    ("path", "patch_target", "service_return", "message_key"),
    [
        (
            "/api/v1/products",
            "app.api.api_v1.endpoints.product_api.ProductQueryService.list_products",
            ([], None, False),
            Msg.PRODUCTS_FETCHED_SUCCESSFULLY,
        ),
        (
            f"/api/v1/products/{PydanticObjectId()}",
            "app.api.api_v1.endpoints.product_api.ProductQueryService.get_product",
            {
                "_id": str(PydanticObjectId()),
                "name": "Phone",
                "description": "Phone description",
                "brand": "Acme",
                "category": {"_id": str(PydanticObjectId()), "name": "Electronics"},
                "variants": [],
                "price": 100,
                "images": [],
                "average_rating": 0,
                "num_reviews": 0,
                "rating_sum": 0,
                "rating_breakdown": {},
                "specifications": {},
                "is_available": True,
                "is_featured": False,
            },
            Msg.PRODUCT_FETCHED_SUCCESSFULLY,
        ),
        (
            "/api/v1/categories/tree",
            "app.api.api_v1.endpoints.category_api.CategoryService.get_category_tree",
            [],
            Msg.CATEGORY_TREE_FETCHED_SUCCESSFULLY,
        ),
        (
            "/api/v1/categories",
            "app.api.api_v1.endpoints.category_api.CategoryService.get_all_categories",
            [],
            Msg.CATEGORIES_FETCHED_SUCCESSFULLY,
        ),
        (
            f"/api/v1/categories/{PydanticObjectId()}",
            "app.api.api_v1.endpoints.category_api.CategoryService.get_category_by_id",
            {"_id": str(PydanticObjectId()), "name": "Electronics", "parent_id": None},
            Msg.CATEGORY_FETCHED_SUCCESSFULLY,
        ),
        (
            f"/api/v1/reviews/products/{PydanticObjectId()}/reviews",
            "app.api.api_v1.endpoints.review_api.ReviewService.list_product_reviews",
            ([], None, False),
            Msg.REVIEWS_FETCHED_SUCCESSFULLY,
        ),
    ],
)
def test_public_catalog_routes_use_accept_language(
    client,
    path: str,
    patch_target: str,
    service_return: Any,
    message_key: str,
):
    with patch(patch_target, new=AsyncMock(return_value=service_return)):
        response = client.get(path, headers={"Accept-Language": "hi"})

    assert response.status_code == 200
    assert response.json()["message"] == _message(message_key, "hi")


def test_public_review_fetch_localizes_message_but_not_user_content(client):
    review_text = "Please keep this review exactly as written."
    with patch(
        "app.api.api_v1.endpoints.review_api.ReviewService.list_product_reviews",
        new=AsyncMock(return_value=([_review_payload(review_text)], None, False)),
    ):
        response = client.get(
            f"/api/v1/reviews/products/{PydanticObjectId()}/reviews",
            headers={"Accept-Language": "ja"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == _message(Msg.REVIEWS_FETCHED_SUCCESSFULLY, "ja")
    assert body["data"]["items"][0]["review"] == review_text


@pytest.mark.parametrize(
    ("preferred_language", "headers", "expected_language"),
    [
        ("hi", {"Accept-Language": "ja"}, "hi"),
        (None, {"Accept-Language": "ja"}, "ja"),
        (None, {}, "en"),
    ],
)
def test_users_me_language_priority(client, preferred_language: str | None, headers: dict[str, str], expected_language: str):
    main.app.dependency_overrides[get_current_user] = _current_user(preferred_language=preferred_language)

    with patch(
        "app.api.api_v1.endpoints.users_api.UserServices.get_my_profile",
        new=AsyncMock(return_value=_user_payload()),
    ):
        response = client.get("/api/v1/users/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["message"] == _message(Msg.CURRENT_USER_FETCHED_SUCCESSFULLY, expected_language)


@pytest.mark.parametrize(
    ("path", "method", "role", "patch_target", "service_return", "message_key", "json_body"),
    [
        (
            "/api/v1/cart",
            "get",
            UserRole.CUSTOMER,
            "app.api.api_v1.endpoints.cart_api.CartService.get_cart",
            {"items": [], "total_quantity": 0, "total_price": 0},
            Msg.CART_FETCHED_SUCCESSFULLY,
            None,
        ),
        (
            "/api/v1/notifications/unread-count",
            "get",
            UserRole.CUSTOMER,
            "app.api.api_v1.endpoints.notification_api.NotificationService.get_unread_count",
            3,
            Msg.UNREAD_NOTIFICATION_COUNT_FETCHED_SUCCESSFULLY,
            None,
        ),
        (
            "/api/v1/device-tokens",
            "post",
            UserRole.CUSTOMER,
            "app.api.api_v1.endpoints.device_token_api.DeviceTokenService.register_token",
            None,
            Msg.DEVICE_TOKEN_REGISTERED_SUCCESSFULLY,
            {"token": "abcdefghijk", "platform": "ANDROID"},
        ),
        (
            "/api/v1/wishlist",
            "get",
            UserRole.CUSTOMER,
            "app.api.api_v1.endpoints.wishlist_api.WishlistService.get_user_wishlist",
            [],
            Msg.WISHLIST_FETCHED_SUCCESSFULLY,
            None,
        ),
        (
            f"/api/v1/reviews/products/{PydanticObjectId()}",
            "post",
            UserRole.CUSTOMER,
            "app.api.api_v1.endpoints.review_api.ReviewService.create_review",
            _review_payload(),
            Msg.REVIEW_CREATED_SUCCESSFULLY,
            {"rating": 5, "review": "Original user text", "images": []},
        ),
        (
            "/api/v1/dashboard/seller/summary",
            "get",
            UserRole.SELLER,
            "app.api.api_v1.endpoints.dashboard_api.DashboardService.get_seller_summary",
            {"total_products": 1, "total_orders": 2},
            Msg.SELLER_DASHBOARD_SUMMARY_FETCHED_SUCCESSFULLY,
            None,
        ),
        (
            f"/api/v1/inventory/products/{PydanticObjectId()}/variants/SKU-1",
            "get",
            UserRole.SELLER,
            "app.api.api_v1.endpoints.inventory_api.InventoryService.get_variant_inventory",
            {
                "product_id": str(PydanticObjectId()),
                "sku": "SKU-1",
                "available_stock": 5,
                "reserved_stock": 1,
                "total_stock": 6,
            },
            Msg.INVENTORY_FETCHED_SUCCESSFULLY,
            None,
        ),
        (
            "/api/v1/orders",
            "get",
            UserRole.CUSTOMER,
            "app.api.api_v1.endpoints.order_api.OrderService.get_my_orders",
            [],
            Msg.ORDER_HISTORY_FETCHED_SUCCESSFULLY,
            None,
        ),
    ],
)
def test_authenticated_routes_prefer_user_language_over_accept_language(
    client,
    path: str,
    method: str,
    role: UserRole,
    patch_target: str,
    service_return: Any,
    message_key: str,
    json_body: dict[str, Any] | None,
):
    main.app.dependency_overrides[get_current_user] = _current_user(role=role, preferred_language="hi")

    with patch(patch_target, new=AsyncMock(return_value=service_return)):
        request = getattr(client, method)
        kwargs: dict[str, Any] = {"headers": {"Accept-Language": "ja"}}
        if json_body is not None:
            kwargs["json"] = json_body
        response = request(path, **kwargs)

    assert response.status_code in {200, 201}
    assert response.json()["message"] == _message(message_key, "hi")


def test_logout_uses_authenticated_user_language_over_accept_language(client):
    async def _bearer_token():
        return "access.token"

    main.app.dependency_overrides[get_current_user] = _current_user(preferred_language="hi")
    main.app.dependency_overrides[get_bearer_token] = _bearer_token

    with patch("app.api.api_v1.endpoints.auth_api.UserServices.logout_user", new=AsyncMock()):
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "refresh.token"},
            headers={"Accept-Language": "ja"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == _message(Msg.USER_LOGGED_OUT_SUCCESSFULLY, "hi")


@pytest.mark.parametrize(
    ("headers", "expected_language"),
    [
        ({"Accept-Language": "hi"}, "hi"),
        ({"Accept-Language": "ja"}, "ja"),
        ({}, "en"),
    ],
)
def test_validation_error_message_is_localized(client, headers: dict[str, str], expected_language: str):
    response = client.get("/api/v1/products", params={"min_price": 100, "max_price": 50}, headers=headers)

    assert response.status_code == 422
    assert response.json()["message"] == _message(Msg.VALIDATION_FAILED, expected_language)


def test_negative_msg_key_errors_are_localized(client):
    with patch(
        "app.api.api_v1.endpoints.product_api.ProductQueryService.get_product",
        new=AsyncMock(return_value=None),
    ):
        response = client.get(f"/api/v1/products/{PydanticObjectId()}", headers={"Accept-Language": "ja"})

    assert response.status_code == 404
    assert response.json()["message"] == _message(Msg.PRODUCT_NOT_FOUND, "ja")


def test_inventory_bad_request_error_uses_authenticated_language_priority(client):
    main.app.dependency_overrides[get_current_user] = _current_user(role=UserRole.ADMIN, preferred_language="hi")

    response = client.get(
        f"/api/v1/inventory/products/{PydanticObjectId()}/variants/SKU-1",
        headers={"Accept-Language": "ja"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == _message(Msg.SELLER_ID_REQUIRED_FOR_ADMIN_INVENTORY_ACCESS, "hi")


def test_unauthenticated_protected_endpoint_returns_401_envelope(client):
    response = client.get("/api/v1/cart", headers={"Accept-Language": "ja"})

    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"
    assert isinstance(body["message"], str)


def test_endpoint_files_do_not_use_hardcoded_success_or_detail_strings():
    offenders: list[str] = []
    for path in ENDPOINTS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if 'success_response("' in text or 'detail="' in text:
            offenders.append(str(path))

    assert offenders == []


def test_endpoint_files_do_not_duplicate_authenticated_language_helper():
    offenders: list[str] = []
    for path in ENDPOINTS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "def _user_language" in text or "from app.core.i18n import get_language" in text:
            offenders.append(str(path))

    assert offenders == []
