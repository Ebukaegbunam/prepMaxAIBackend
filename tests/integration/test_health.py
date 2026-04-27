"""Integration tests for /health and /ready endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _make_app(monkeypatch, openai_key: str = "sk-test"):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-jwt-secret-must-be-at-least-32-chars-long!")
    monkeypatch.setenv("OPENAI_API_KEY", openai_key)
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:test@localhost:5432/test")

    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import create_app
    return create_app()


def _mock_engine_ok() -> MagicMock:
    """Mock SQLAlchemy engine that succeeds SELECT 1."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    engine = MagicMock()
    engine.connect = MagicMock(return_value=mock_cm)
    return engine


def _mock_engine_fail() -> MagicMock:
    """Mock SQLAlchemy engine that raises on connect."""
    engine = MagicMock()
    engine.connect.side_effect = Exception("Connection refused")
    return engine


def _mock_http_ok() -> AsyncMock:
    """Mock httpx.AsyncClient that returns 200 for the storage check."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client


async def test_health_returns_200(monkeypatch):
    app = _make_app(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert isinstance(body["uptime_seconds"], float | int)


async def test_health_no_auth_required(monkeypatch):
    app = _make_app(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200


async def test_health_includes_request_id_header(monkeypatch):
    app = _make_app(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert "X-Request-ID" in response.headers


async def test_ready_returns_200_when_all_checks_pass(monkeypatch):
    app = _make_app(monkeypatch)
    with (
        patch("app.routes.health.get_engine", return_value=_mock_engine_ok()),
        patch("app.routes.health.httpx.AsyncClient", return_value=_mock_http_ok()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["llm_provider"] == "ok"
    assert body["checks"]["storage"] == "ok"


async def test_ready_returns_503_when_db_fails(monkeypatch):
    app = _make_app(monkeypatch)
    with (
        patch("app.routes.health.get_engine", return_value=_mock_engine_fail()),
        patch("app.routes.health.httpx.AsyncClient", return_value=_mock_http_ok()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "error"


async def test_ready_returns_503_when_llm_key_missing(monkeypatch):
    app = _make_app(monkeypatch, openai_key="")  # empty key
    with (
        patch("app.routes.health.get_engine", return_value=_mock_engine_ok()),
        patch("app.routes.health.httpx.AsyncClient", return_value=_mock_http_ok()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["llm_provider"] == "error"
