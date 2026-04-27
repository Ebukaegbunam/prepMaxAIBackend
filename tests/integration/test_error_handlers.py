"""Integration tests for global error handlers: cost cap, LLM errors."""
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

_SECRET = "test-jwt-secret-must-be-at-least-32-chars-long!"
_USER_ID = str(uuid.uuid4())


def _make_token(user_id: str = _USER_ID) -> str:
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated", "role": "authenticated", "exp": int(time.time()) + 3600},
        _SECRET, algorithm="HS256",
    )


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token()}"}


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
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")
    from app.main import create_app
    return create_app()


@pytest.mark.anyio
async def test_cost_cap_exceeded_returns_429(monkeypatch):
    """CostCapExceededError propagating from an AI route → 429 with structured error."""
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    from app.llm.base import CostCapExceededError

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.llm.router.execute", AsyncMock(side_effect=CostCapExceededError("Daily AI spend cap of $5.00 exceeded"))):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.post(
                "/ai/parse-workout",
                headers=_auth(),
                json={"prep_id": str(uuid.uuid4()), "text": "bench press 3x10"},
            )

    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["code"] == "cost_cap_exceeded"
    assert "exceeded" in body["error"]["message"].lower()


@pytest.mark.anyio
async def test_llm_provider_error_returns_502(monkeypatch):
    """LLMError propagating from an AI route → 502 with structured error."""
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    from app.llm.base import LLMError

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.llm.router.execute", AsyncMock(side_effect=LLMError("upstream provider timeout"))):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.post(
                "/ai/parse-workout",
                headers=_auth(),
                json={"prep_id": str(uuid.uuid4()), "text": "bench press 3x10"},
            )

    assert resp.status_code == 502
    body = resp.json()
    assert body["error"]["code"] == "ai_provider_error"


@pytest.mark.anyio
async def test_unhandled_exception_returns_500(monkeypatch):
    """Unexpected exceptions → 500 internal_error. Use raise_app_exceptions=False
    so the propagated exception from ServerErrorMiddleware doesn't fail the test."""
    application = _make_app(monkeypatch)
    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    transport = ASGITransport(app=application, raise_app_exceptions=False)
    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.llm.router.execute", AsyncMock(side_effect=RuntimeError("unexpected failure"))):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/ai/parse-workout",
                headers=_auth(),
                json={"prep_id": str(uuid.uuid4()), "text": "bench press 3x10"},
            )

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "internal_error"
