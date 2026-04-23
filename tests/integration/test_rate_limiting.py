from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.rate_limiter import get_user_or_ip_key, ip_key_func
from app.core.security import create_access_token


def _clear_limiter_storage(limiter: Limiter) -> None:
    storage = getattr(limiter, "_storage", None)
    if storage is None:
        return

    for attr in ("storage", "expirations", "events"):
        data = getattr(storage, attr, None)
        clear = getattr(data, "clear", None)
        if callable(clear):
            clear()


def _make_test_app(limiter: Limiter) -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(_request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"message": "Rate limit exceeded", "detail": exc.detail},
        )

    @app.get("/ip")
    @limiter.limit("2/minute", key_func=ip_key_func)
    async def ip_limited(request: Request):
        return {"ok": True, "client": request.client.host if request.client else None}

    @app.get("/user")
    @limiter.limit("2/minute")
    async def user_or_ip_limited(request: Request):
        return {"ok": True}

    return app


def test_rate_limit_ip_scoped():
    limiter = Limiter(key_func=get_user_or_ip_key)
    _clear_limiter_storage(limiter)
    app = _make_test_app(limiter)

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/ip").status_code == 200
        assert client.get("/ip").status_code == 200

        resp = client.get("/ip")
        assert resp.status_code == 429
        assert resp.json()["message"] == "Rate limit exceeded"


def test_rate_limit_user_token_scoped_and_isolated():
    limiter = Limiter(key_func=get_user_or_ip_key)
    _clear_limiter_storage(limiter)
    app = _make_test_app(limiter)

    token_a = create_access_token({"user_id": "user-a"})
    token_b = create_access_token({"user_id": "user-b"})

    with TestClient(app, raise_server_exceptions=False) as client:
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        assert client.get("/user", headers=headers_a).status_code == 200
        assert client.get("/user", headers=headers_a).status_code == 200
        assert client.get("/user", headers=headers_a).status_code == 429

        # Different user gets a fresh bucket.
        assert client.get("/user", headers=headers_b).status_code == 200


def test_rate_limit_invalid_token_falls_back_to_ip_bucket():
    limiter = Limiter(key_func=get_user_or_ip_key)
    _clear_limiter_storage(limiter)
    app = _make_test_app(limiter)

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/user").status_code == 200
        assert client.get("/user").status_code == 200

        # Invalid token should not create a distinct user bucket.
        resp = client.get("/user", headers={"Authorization": "Bearer not-a-jwt"})
        assert resp.status_code == 429


def test_main_root_endpoint_is_rate_limited_by_ip(client):
    import app.main as main

    _clear_limiter_storage(main.limiter)

    for _ in range(5):
        resp = client.get("/")
        assert resp.status_code == 200

    resp = client.get("/")
    assert resp.status_code == 429
    payload = resp.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Rate limit exceeded"
