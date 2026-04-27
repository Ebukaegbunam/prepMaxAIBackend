"""Integration tests for /__test__/ui — Phase 8 Test UI."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _make_db_mock():
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_cm), mock_db


@pytest.mark.anyio
async def test_ui_loads_in_non_prod(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-must-be-at-least-32-chars-long!")
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()
    mock_factory, _ = _make_db_mock()

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/__test__/ui")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "PrepAI" in resp.text


@pytest.mark.anyio
async def test_ui_returns_404_in_production(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-must-be-at-least-32-chars-long!")
    monkeypatch.setenv("APP_ENV", "production")

    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import create_app
    application = create_app()
    mock_factory, _ = _make_db_mock()

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/__test__/ui")

    assert resp.status_code == 404
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_static_presets_accessible_in_non_prod(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-must-be-at-least-32-chars-long!")
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()
    mock_factory, _ = _make_db_mock()

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/static/test_ui/presets.json")

    assert resp.status_code == 200
    data = resp.json()
    assert "profile_initialize" in data
    assert "parse_workout" in data
