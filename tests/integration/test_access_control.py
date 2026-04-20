from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.dependencies import get_current_user
from app.core.user_role import UserRole
from app.services.user_services import UserServices
from app.main import app


def _override_user(role: UserRole):
    return lambda: SimpleNamespace(
        id="507f1f77bcf86cd799439011",
        email="user@example.com",
        role=role,
        addresses=[],
    )


def test_category_create_forbidden_for_customer(client):
    app.dependency_overrides[get_current_user] = _override_user(UserRole.CUSTOMER)

    response = client.post("/api/v1/admin/categories/", json={"name": "Electronics"})

    assert response.status_code == 403
    assert response.json()["message"] == "You do not have permission to perform this action"


def test_get_all_users_forbidden_for_customer(client):
    app.dependency_overrides[get_current_user] = _override_user(UserRole.CUSTOMER)

    response = client.get("/api/v1/admin/users/")

    assert response.status_code == 403
    assert response.json()["message"] == "You do not have permission to perform this action"


def test_get_all_users_allows_admin(client, monkeypatch):
    app.dependency_overrides[get_current_user] = _override_user(UserRole.ADMIN)
    monkeypatch.setattr(UserServices, "get_all_users", AsyncMock(return_value=[]))

    response = client.get("/api/v1/admin/users/")

    assert response.status_code == 200
    assert response.json()["data"] == []
