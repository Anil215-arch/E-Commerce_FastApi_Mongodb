from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId

import main
from app.core.dependencies import get_bearer_token, get_current_user


def test_register_user_route_returns_success_envelope(client):
    created_user = {
        "_id": str(PydanticObjectId()),
        "user_name": "john",
        "email": "john@example.com",
        "mobile": "9876543210",
        "role": "customer",
        "is_verified": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with patch("app.api.api_v1.endpoints.user_api.UserServices.user_registration", new=AsyncMock(return_value=created_user)):
        response = client.post(
            "/api/v1/users/register",
            json={
                "user_name": "john",
                "email": "john@example.com",
                "password": "StrongPass123!",
                "mobile": "9876543210",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["email"] == "john@example.com"


def test_login_user_route_returns_tokens(client):
    token_payload = {
        "access_token": "access.token",
        "refresh_token": "refresh.token",
        "token_type": "bearer",
    }

    with patch("app.api.api_v1.endpoints.user_api.UserServices.login_and_issue_tokens", new=AsyncMock(return_value=token_payload)):
        response = client.post(
            "/api/v1/users/login",
            json={"email": "john@example.com", "password": "StrongPass123!"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["access_token"] == "access.token"


def test_refresh_route_maps_service_http_error_to_standard_error_envelope(client):
    from fastapi import HTTPException

    with patch(
        "app.api.api_v1.endpoints.user_api.UserServices.refresh_user_token",
        new=AsyncMock(side_effect=HTTPException(status_code=401, detail="Refresh token has been revoked")),
    ):
        response = client.post("/api/v1/users/refresh", json={"refresh_token": "revoked"})

    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"
    assert "revoked" in body["message"].lower()


def test_logout_route_success_with_dependency_overrides(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    def _bearer_token():
        return "access.token"

    main.app.dependency_overrides[get_current_user] = _current_user
    main.app.dependency_overrides[get_bearer_token] = _bearer_token

    with patch("app.api.api_v1.endpoints.user_api.UserServices.logout_user", new=AsyncMock()) as mock_logout:
        response = client.post("/api/v1/users/logout", json={"refresh_token": "refresh.token"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    mock_logout.assert_awaited_once()


def test_forgot_password_route_returns_generic_message(client):
    with patch("app.api.api_v1.endpoints.email_otp_api.UserServices.forgot_password_request", new=AsyncMock()) as mock_forgot:
        response = client.post("/api/v1/auth/forgot-password", json={"email": "john@example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "associated with this email" in body["message"].lower()
    mock_forgot.assert_awaited_once()


def test_verify_registration_route_uses_service_message(client):
    with patch(
        "app.api.api_v1.endpoints.email_otp_api.UserServices.verify_email_registration",
        new=AsyncMock(return_value="Email verified successfully. You can now login."),
    ):
        response = client.post(
            "/api/v1/auth/verify-registration",
            json={"email": "john@example.com", "otp_code": "123456"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "verified" in body["message"].lower()
