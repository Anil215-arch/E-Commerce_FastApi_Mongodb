from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

import app.main as main
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

    with patch("app.api.api_v1.endpoints.public.auth.UserServices.user_registration", new=AsyncMock(return_value=created_user)):
        response = client.post(
            "/api/v1/auth/register",
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

    with patch("app.api.api_v1.endpoints.public.auth.UserServices.login_and_issue_tokens", new=AsyncMock(return_value=token_payload)):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "john@example.com", "password": "StrongPass123!"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["access_token"] == "access.token"


def test_refresh_route_maps_service_http_error_to_standard_error_envelope(client):
    from fastapi import HTTPException

    with patch(
        "app.api.api_v1.endpoints.public.auth.UserServices.refresh_user_token",
        new=AsyncMock(side_effect=HTTPException(status_code=401, detail="Refresh token has been revoked")),
    ):
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "revoked"})

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

    with patch("app.api.api_v1.endpoints.public.auth.UserServices.logout_user", new=AsyncMock()) as mock_logout:
        response = client.post("/api/v1/auth/logout", json={"refresh_token": "refresh.token"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    mock_logout.assert_awaited_once()


def test_forgot_password_route_returns_generic_message(client):
    with patch("app.api.api_v1.endpoints.public.auth.UserServices.forgot_password_request", new=AsyncMock()) as mock_forgot:
        response = client.post("/api/v1/auth/forgot-password", json={"email": "john@example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "associated with this email" in body["message"].lower()
    mock_forgot.assert_awaited_once()


def test_verify_registration_route_uses_service_message(client):
    with patch(
        "app.api.api_v1.endpoints.public.auth.UserServices.verify_email_registration",
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


def _address_payload(city: str = "Bengaluru") -> dict:
    return {
        "address": {
            "full_name": "John Doe",
            "phone_number": "9876543210",
            "street_address": "123 Main Street",
            "city": city,
            "postal_code": "560001",
            "state": "Karnataka",
            "country": "India",
        }
    }


def _user_response_with_addresses(addresses: list[dict]) -> dict:
    return {
        "_id": str(PydanticObjectId()),
        "user_name": "john",
        "email": "john@example.com",
        "mobile": "9876543210",
        "role": "customer",
        "is_verified": True,
        "addresses": addresses,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_add_address_route_returns_success_envelope(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    service_result = _user_response_with_addresses([_address_payload()["address"]])

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.add_user_address",
        new=AsyncMock(return_value=service_result),
    ) as mock_add:
        response = client.post("/api/v1/customer/profile/addresses", json=_address_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "address added" in body["message"].lower()
    assert body["data"]["addresses"][0]["city"] == "Bengaluru"

    await_args = mock_add.await_args
    assert await_args is not None
    assert await_args.args[1].address.city == "Bengaluru"


def test_update_address_route_passes_index_and_payload(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    service_result = _user_response_with_addresses([_address_payload(city="Mysuru")["address"]])

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.update_user_address",
        new=AsyncMock(return_value=service_result),
    ) as mock_update:
        response = client.patch("/api/v1/customer/profile/addresses/0", json=_address_payload(city="Mysuru"))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "address updated" in body["message"].lower()
    assert body["data"]["addresses"][0]["city"] == "Mysuru"

    await_args = mock_update.await_args
    assert await_args is not None
    assert await_args.args[1] == 0
    assert await_args.args[2].address.city == "Mysuru"


def test_remove_address_route_returns_updated_user(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    service_result = _user_response_with_addresses([])

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.remove_user_address",
        new=AsyncMock(return_value=service_result),
    ) as mock_remove:
        response = client.delete("/api/v1/customer/profile/addresses/0")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "address removed" in body["message"].lower()
    assert body["data"]["addresses"] == []

    await_args = mock_remove.await_args
    assert await_args is not None
    assert await_args.args[1] == 0


def test_update_address_route_surfaces_not_found_error(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.update_user_address",
        new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Address not found at the specified index.")),
    ):
        response = client.patch("/api/v1/customer/profile/addresses/99", json=_address_payload())

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert "address not found" in body["message"].lower()


@pytest.mark.parametrize("bad_phone", ["12345", "123456789"])
def test_add_address_route_returns_422_for_short_phone(client, bad_phone):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    payload = _address_payload()
    payload["address"]["phone_number"] = bad_phone

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.add_user_address",
        new=AsyncMock(),
    ) as mock_add:
        response = client.post("/api/v1/customer/profile/addresses", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    mock_add.assert_not_awaited()


def test_add_address_route_returns_422_for_missing_city(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    payload = _address_payload()
    payload["address"].pop("city")

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.add_user_address",
        new=AsyncMock(),
    ) as mock_add:
        response = client.post("/api/v1/customer/profile/addresses", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    mock_add.assert_not_awaited()


def test_update_address_route_returns_422_for_missing_city(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    payload = _address_payload(city="Mysuru")
    payload["address"].pop("city")

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.update_user_address",
        new=AsyncMock(),
    ) as mock_update:
        response = client.patch("/api/v1/customer/profile/addresses/0", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    mock_update.assert_not_awaited()


def test_update_address_route_returns_422_for_non_integer_index(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.update_user_address",
        new=AsyncMock(),
    ) as mock_update:
        response = client.patch("/api/v1/customer/profile/addresses/not-a-number", json=_address_payload())

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    mock_update.assert_not_awaited()


def test_remove_address_route_returns_422_for_non_integer_index(client):
    async def _current_user():
        return SimpleNamespace(id=PydanticObjectId(), email="john@example.com")

    main.app.dependency_overrides[get_current_user] = _current_user

    with patch(
        "app.api.api_v1.endpoints.customer.profile.UserServices.remove_user_address",
        new=AsyncMock(),
    ) as mock_remove:
        response = client.delete("/api/v1/customer/profile/addresses/not-a-number")

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["message"] == "Validation failed"
    mock_remove.assert_not_awaited()
