"""Integration tests for /preps endpoints."""
import time
import uuid
from datetime import date
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


def _mock_prep(user_id: str = _USER_ID) -> MagicMock:
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    p = MagicMock()
    p.id = uuid.uuid4()
    p.user_id = uuid.UUID(user_id)
    p.division = "classic_physique"
    p.prep_length_weeks = 16
    p.start_date = date(2026, 5, 4)
    p.target_date = date(2026, 8, 24)
    p.target_competition_id = None
    p.status = "active"
    p.starting_weight_kg = 84.5
    p.target_weight_kg = 78.0
    p.starting_bf_pct = 14.0
    p.target_bf_pct = 7.0
    p.phase_split = {"maintenance_weeks": 4, "cut_weeks": 12}
    p.current_workout_template_id = None
    p.current_weekly_plan_id = None
    p.completion_notes = None
    p.created_at = now
    p.updated_at = now
    return p


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


@pytest.fixture
def app():
    import os
    os.environ.update({
        "APP_ENV": "test", "SUPABASE_JWT_SECRET": _SECRET,
        "SUPABASE_URL": "https://test.supabase.co", "SUPABASE_ANON_KEY": "test",
        "SUPABASE_SERVICE_ROLE_KEY": "test", "OPENAI_API_KEY": "sk-test",
        "DATABASE_URL": "postgresql+asyncpg://postgres:test@localhost/test",
    })
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import create_app
    return create_app()


@pytest.fixture
async def client(app):
    from app.db.session import get_db
    mock_factory, mock_db = _make_db_mock()

    async def _mock_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_get_db
    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    app.dependency_overrides.clear()


pytestmark = pytest.mark.anyio


class TestListPreps:
    async def test_no_auth_returns_401(self, client):
        resp = await client.get("/preps")
        assert resp.status_code == 401

    async def test_returns_list(self, client):
        prep = _mock_prep()
        with patch("app.services.prep_service.list_preps", new=AsyncMock(return_value=[prep])):
            resp = await client.get("/preps", headers=_auth())
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 1


class TestCreatePrep:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post("/preps", json={"division": "classic_physique", "start_date": "2026-05-04"})
        assert resp.status_code == 401

    async def test_creates_prep(self, client):
        prep = _mock_prep()
        with patch("app.services.prep_service.create_prep", new=AsyncMock(return_value=prep)):
            resp = await client.post(
                "/preps",
                json={"division": "classic_physique", "start_date": "2026-05-04"},
                headers=_auth(),
            )
        assert resp.status_code == 201
        assert resp.json()["division"] == "classic_physique"

    async def test_invalid_division_returns_422(self, client):
        resp = await client.post(
            "/preps",
            json={"division": "power_lifting", "start_date": "2026-05-04"},
            headers=_auth(),
        )
        assert resp.status_code == 422

    async def test_missing_start_date_returns_422(self, client):
        resp = await client.post(
            "/preps",
            json={"division": "classic_physique"},
            headers=_auth(),
        )
        assert resp.status_code == 422


class TestGetPrep:
    async def test_not_found_returns_404(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=None)):
            resp = await client.get(f"/preps/{uuid.uuid4()}", headers=_auth())
        assert resp.status_code == 404

    async def test_returns_prep(self, client):
        prep = _mock_prep()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=prep)):
            resp = await client.get(f"/preps/{prep.id}", headers=_auth())
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


class TestCompletePrep:
    async def test_complete_sets_status(self, client):
        prep = _mock_prep()
        completed = _mock_prep()
        completed.status = "completed"
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=prep)):
            with patch("app.services.prep_service.complete_prep", new=AsyncMock(return_value=completed)):
                resp = await client.post(
                    f"/preps/{prep.id}/complete",
                    json={"completion_notes": "Hit stage at 78kg"},
                    headers=_auth(),
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
