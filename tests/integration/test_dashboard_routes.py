from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId

import main
from app.core.dependencies import get_current_user
from app.core.user_role import UserRole


def _override_user(role: UserRole, user_id: PydanticObjectId | None = None):
    resolved_id = user_id or PydanticObjectId()

    async def _user():
        return SimpleNamespace(
            id=resolved_id,
            role=role,
            email="dashboard@example.com",
            addresses=[],
        )

    return _user


def test_seller_dashboard_summary_success(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER)

    with patch(
        "app.api.api_v1.endpoints.seller.dashboard.DashboardService.get_seller_summary",
        new=AsyncMock(return_value={"total_products": 5, "total_orders": 9}),
    ):
        response = client.get("/api/v1/seller/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message"] == "Seller dashboard summary fetched successfully"
    assert body["data"]["total_products"] == 5
    assert body["data"]["total_orders"] == 9


def test_seller_dashboard_revenue_success(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER)

    with patch(
        "app.api.api_v1.endpoints.seller.dashboard.DashboardService.get_revenue_chart",
        new=AsyncMock(return_value=[{"date": "2026-04-01", "revenue": 1200}]),
    ):
        response = client.get("/api/v1/seller/dashboard/revenue?period=daily")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message"] == "Seller revenue data fetched"
    assert body["data"]["data"][0]["date"] == "2026-04-01"
    assert body["data"]["data"][0]["revenue"] == 1200


def test_seller_dashboard_revenue_maps_value_error_to_400(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER)

    with patch(
        "app.api.api_v1.endpoints.seller.dashboard.DashboardService.get_revenue_chart",
        new=AsyncMock(side_effect=ValueError("Date range exceeds 5-year limit")),
    ):
        response = client.get("/api/v1/seller/dashboard/revenue?period=yearly")

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert "5-year limit" in body["message"]


def test_seller_dashboard_is_forbidden_for_customer(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.CUSTOMER)

    response = client.get("/api/v1/seller/dashboard/summary")

    assert response.status_code == 403
    body = response.json()
    assert body["status"] == "error"
    assert "permission" in body["message"].lower()


def test_admin_dashboard_summary_success(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.ADMIN)

    payload = {
        "total_users": 100,
        "total_sellers": 20,
        "total_orders": 300,
        "total_products": 500,
        "total_categories": 40,
    }

    with patch(
        "app.api.api_v1.endpoints.admin.dashboard.DashboardService.get_admin_summary",
        new=AsyncMock(return_value=payload),
    ):
        response = client.get("/api/v1/admin/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message"] == "Admin dashboard summary fetched successfully"
    assert body["data"]["total_users"] == 100


def test_admin_dashboard_revenue_success(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.ADMIN)

    with patch(
        "app.api.api_v1.endpoints.admin.dashboard.DashboardService.get_revenue_chart",
        new=AsyncMock(return_value=[{"date": "2026-04", "revenue": 3400}]),
    ):
        response = client.get("/api/v1/admin/dashboard/revenue?period=monthly")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message"] == "Admin revenue data fetched"
    assert body["data"]["data"][0]["date"] == "2026-04"
    assert body["data"]["data"][0]["revenue"] == 3400


def test_admin_dashboard_is_forbidden_for_seller(client):
    main.app.dependency_overrides[get_current_user] = _override_user(UserRole.SELLER)

    response = client.get("/api/v1/admin/dashboard/summary")

    assert response.status_code == 403
    body = response.json()
    assert body["status"] == "error"
    assert "permission" in body["message"].lower()
