"""Root conftest: sets test environment variables before any app module is imported."""
import os

# Set test env vars before importing app modules — config reads from env at import time.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-must-be-at-least-32-chars-long!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:test@localhost:5432/prepai_test")

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def app():
    # Clear settings cache so env vars above take effect
    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import create_app
    return create_app()


@pytest.fixture
async def async_client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
