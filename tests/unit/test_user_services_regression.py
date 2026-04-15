from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.core.user_role import UserRole
from app.schemas.user_schema import RefreshTokenRequest, UserRegister, UserUpdateRole
from app.services.user_services import UserServices


@pytest.fixture(autouse=True)
def _stub_beanie_expression_fields():
    with patch("app.services.user_services.User.email", new=object(), create=True):
        with patch("app.services.user_services.User.user_name", new=object(), create=True):
            with patch("app.services.user_services.User.id", new=object(), create=True):
                with patch("app.services.user_services.User.role", new=object(), create=True):
                    with patch("app.services.user_services.RevokedToken.jti", new=object(), create=True):
                        yield


@pytest.mark.asyncio
async def test_user_registration_existing_unverified_user_resends_otp_and_raises():
    existing_user = SimpleNamespace(email="existing@example.com", is_verified=False)

    with patch("app.services.user_services.User.find_one", new=AsyncMock(return_value=existing_user)):
        with patch("app.services.user_services.OTPService.create_and_send_otp", new=AsyncMock()) as mock_send:
            with pytest.raises(HTTPException) as exc:
                await UserServices.user_registration(
                    UserRegister(
                        user_name="newuser",
                        email="existing@example.com",
                        password="StrongPass123!",
                        mobile="9876543210",
                    )
                )

    assert exc.value.status_code == 400
    assert "not verified" in str(exc.value.detail).lower()
    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_registration_duplicate_username_raises():
    with patch("app.services.user_services.User.find_one", new=AsyncMock(side_effect=[None, object()])):
        with pytest.raises(HTTPException) as exc:
            await UserServices.user_registration(
                UserRegister(
                    user_name="taken",
                    email="fresh@example.com",
                    password="StrongPass123!",
                    mobile="9876543210",
                )
            )

    assert exc.value.status_code == 400
    assert "username already taken" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_authenticate_user_blocks_unverified_account():
    user = SimpleNamespace(hashed_password="hashed", is_verified=False)

    with patch("app.services.user_services.User.find_one", new=AsyncMock(return_value=user)):
        with patch("app.services.user_services.verify_password", return_value=True):
            with pytest.raises(HTTPException) as exc:
                await UserServices._authenticate_user("u@example.com", "StrongPass123!")

    assert exc.value.status_code == 403
    assert "not verified" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_refresh_user_token_rejects_revoked_token():
    token_data = SimpleNamespace(email="u@example.com", jti="revoked-jti", token_type="refresh")

    with patch(
        "app.services.user_services.UserServices._decode_token_data",
        new=AsyncMock(return_value=(token_data, datetime.now(timezone.utc))),
    ):
        with patch("app.services.user_services.RevokedToken.find_one", new=AsyncMock(return_value=object())):
            with pytest.raises(HTTPException) as exc:
                await UserServices.refresh_user_token(RefreshTokenRequest(refresh_token="revoked.token"))

    assert exc.value.status_code == 401
    assert "revoked" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_logout_rejects_refresh_token_for_different_user():
    current_user = SimpleNamespace(email="owner@example.com")
    access_data = SimpleNamespace(email="owner@example.com", jti="access-jti")
    refresh_data = SimpleNamespace(email="intruder@example.com", jti="refresh-jti")

    with patch(
        "app.services.user_services.UserServices._decode_token_data",
        new=AsyncMock(
            side_effect=[
                (access_data, datetime.now(timezone.utc)),
                (refresh_data, datetime.now(timezone.utc)),
            ]
        ),
    ):
        with patch("app.services.user_services.RevokedToken.find_one", new=AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc:
                from app.schemas.user_schema import LogoutRequest

                await UserServices.logout_user(current_user, "access.token", LogoutRequest(refresh_token="bad.refresh"))

    assert exc.value.status_code == 401
    assert "do not belong" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_update_user_role_admin_cannot_assign_admin_role():
    current_user = SimpleNamespace(id=PydanticObjectId(), role=UserRole.ADMIN)
    target_user = SimpleNamespace(id=PydanticObjectId(), role=UserRole.CUSTOMER)

    with patch("app.services.user_services.User.get", new=AsyncMock(return_value=target_user)):
        with pytest.raises(HTTPException) as exc:
            await UserServices.update_user_role(
                current_user,
                target_user.id,
                UserUpdateRole(new_role=UserRole.ADMIN),
            )

    assert exc.value.status_code == 403
    assert "admins can assign only" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_update_user_role_prevents_second_super_admin():
    current_user = SimpleNamespace(id=PydanticObjectId(), role=UserRole.SUPER_ADMIN)
    target_user = SimpleNamespace(id=PydanticObjectId(), role=UserRole.ADMIN)
    existing_super_admin = SimpleNamespace(id=PydanticObjectId(), role=UserRole.SUPER_ADMIN)

    with patch("app.services.user_services.User.get", new=AsyncMock(return_value=target_user)):
        with patch("app.services.user_services.User.find_one", new=AsyncMock(return_value=existing_super_admin)):
            with pytest.raises(HTTPException) as exc:
                await UserServices.update_user_role(
                    current_user,
                    target_user.id,
                    UserUpdateRole(new_role=UserRole.SUPER_ADMIN),
                )

    assert exc.value.status_code == 400
    assert "only one super admin" in str(exc.value.detail).lower()
