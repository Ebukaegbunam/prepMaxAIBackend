"""Integration tests for /__admin__ endpoints."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

_ADMIN_TOKEN = "test-admin-secret-token"
_USER_ID = str(uuid.uuid4())


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": _ADMIN_TOKEN}


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


def _make_app(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-must-be-at-least-32-chars-long!")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ADMIN_TOKEN", _ADMIN_TOKEN)

    from app.main import create_app
    return create_app()


@pytest.mark.anyio
async def test_cost_rollup_requires_admin_token(monkeypatch):
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            r_no_token = await ac.get("/__admin__/cost-rollup")
            r_wrong_token = await ac.get("/__admin__/cost-rollup", headers={"X-Admin-Token": "wrong"})
            r_valid = await ac.get("/__admin__/cost-rollup", headers=_admin_headers())

    assert r_no_token.status_code == 401
    assert r_wrong_token.status_code == 401
    assert r_valid.status_code == 200


@pytest.mark.anyio
async def test_cost_rollup_response_shape(monkeypatch):
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    rollup_rows = MagicMock()
    rollup_rows.all.return_value = []

    totals_row = MagicMock()
    totals_row.total_cost = 0
    totals_row.total_calls = 0
    totals_result = MagicMock()
    totals_result.one.return_value = totals_row

    call_count = 0

    async def _execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return rollup_rows
        return totals_result

    mock_db.execute.side_effect = _execute_side_effect

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/__admin__/cost-rollup?days=7", headers=_admin_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 7
    assert "since" in body
    assert "total_cost_usd" in body
    assert "total_calls" in body
    assert "breakdown" in body
    assert isinstance(body["breakdown"], list)


@pytest.mark.anyio
async def test_rate_limit_status_requires_admin_token(monkeypatch):
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    scalar_result = MagicMock()
    scalar_result.scalar.return_value = 42
    mock_db.execute.return_value = scalar_result

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    test_user = uuid.uuid4()
    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            r_no_token = await ac.get(f"/__admin__/rate-limit/{test_user}")
            r_valid = await ac.get(f"/__admin__/rate-limit/{test_user}", headers=_admin_headers())

    assert r_no_token.status_code == 401
    assert r_valid.status_code == 200


@pytest.mark.anyio
async def test_rate_limit_status_response_shape(monkeypatch):
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    scalar_result = MagicMock()
    scalar_result.scalar.return_value = 350
    mock_db.execute.return_value = scalar_result

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    test_user = uuid.uuid4()
    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get(f"/__admin__/rate-limit/{test_user}", headers=_admin_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == str(test_user)
    assert body["limit"] == 1000
    assert body["current_count"] == 350
    assert body["remaining"] == 650
    assert body["is_limited"] is False


@pytest.mark.anyio
async def test_rate_limit_shows_is_limited_when_at_cap(monkeypatch):
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    scalar_result = MagicMock()
    scalar_result.scalar.return_value = 1000
    mock_db.execute.return_value = scalar_result

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    test_user = uuid.uuid4()
    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get(f"/__admin__/rate-limit/{test_user}", headers=_admin_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_limited"] is True
    assert body["remaining"] == 0


@pytest.mark.anyio
async def test_health_deep_requires_admin_token(monkeypatch):
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    async def _execute_side(*args, **kwargs):
        r = MagicMock()
        r.scalar.return_value = 0
        return r

    mock_db.execute.side_effect = _execute_side

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            r_no_token = await ac.get("/__admin__/health/deep")
            r_valid = await ac.get("/__admin__/health/deep", headers=_admin_headers())

    assert r_no_token.status_code == 401
    assert r_valid.status_code == 200


@pytest.mark.anyio
async def test_health_deep_response_shape(monkeypatch):
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    call_count = 0

    async def _execute_side(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        r = MagicMock()
        r.scalar.return_value = 0
        return r

    mock_db.execute.side_effect = _execute_side

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/__admin__/health/deep", headers=_admin_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "uptime_seconds" in body
    assert "version" in body
    assert "environment" in body
    assert "checks" in body
    checks = body["checks"]
    assert "database" in checks
    assert "openai_key" in checks
    assert "sentry" in checks
    assert "ai_cost_24h" in checks
