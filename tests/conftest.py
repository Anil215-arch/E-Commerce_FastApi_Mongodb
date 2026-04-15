import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main

# Keep config validation stable in test environments.
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-bytes-123456")

# Make project root importable when pytest is invoked via entrypoint script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    original_overrides = main.app.dependency_overrides.copy()
    original_lifespan = main.app.router.lifespan_context

    async def _fake_init_db() -> None:
        return None

    @asynccontextmanager
    async def no_lifespan(_app):
        yield

    monkeypatch.setattr(main, "init_db", _fake_init_db)
    main.app.dependency_overrides = {}
    main.app.router.lifespan_context = no_lifespan

    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client

    main.app.dependency_overrides = original_overrides
    main.app.router.lifespan_context = original_lifespan
