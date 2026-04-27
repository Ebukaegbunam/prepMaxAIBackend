"""Integration tests for session, set, and cardio-log endpoints."""
import time
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

_SECRET = "test-jwt-secret-must-be-at-least-32-chars-long!"
_USER_ID = str(uuid.uuid4())
_PREP_ID = uuid.uuid4()
_SESSION_ID = uuid.uuid4()
_CANONICAL_ID = uuid.uuid4()


def _make_token(user_id: str = _USER_ID) -> str:
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated", "role": "authenticated", "exp": int(time.time()) + 3600},
        _SECRET, algorithm="HS256",
    )


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token()}"}


def _mock_prep():
    now = datetime.now(timezone.utc)
    p = MagicMock()
    p.id = _PREP_ID
    p.user_id = uuid.UUID(_USER_ID)
    p.division = "classic_physique"
    p.prep_length_weeks = 16
    p.start_date = date(2026, 5, 4)
    p.target_date = date(2026, 8, 24)
    p.status = "active"
    p.phase_split = {"maintenance_weeks": 4, "cut_weeks": 12}
    p.current_workout_template_id = None
    p.current_weekly_plan_id = None
    p.completion_notes = None
    p.created_at = now
    p.updated_at = now
    return p


def _mock_session():
    now = datetime.now(timezone.utc)
    s = MagicMock()
    s.id = _SESSION_ID
    s.user_id = uuid.UUID(_USER_ID)
    s.prep_id = _PREP_ID
    s.workout_day_id = None
    s.title = "Chest Day"
    s.started_at = now
    s.completed_at = None
    s.notes = None
    s.sets = []
    s.created_at = now
    s.updated_at = now
    return s


def _mock_set_log():
    now = datetime.now(timezone.utc)
    s = MagicMock()
    s.id = uuid.uuid4()
    s.user_id = uuid.UUID(_USER_ID)
    s.workout_session_id = _SESSION_ID
    s.exercise_id = None
    s.canonical_exercise_id = _CANONICAL_ID
    s.exercise_name_raw = "Incline DB Press"
    s.set_number = 1
    s.weight_kg = 30.0
    s.reps = 8
    s.rpe = 7.5
    s.performed_at = now
    s.notes = None
    s.created_at = now
    return s


def _mock_cardio_log():
    now = datetime.now(timezone.utc)
    c = MagicMock()
    c.id = uuid.uuid4()
    c.user_id = uuid.UUID(_USER_ID)
    c.prep_id = _PREP_ID
    c.performed_at = now
    c.modality = "incline_walk"
    c.duration_min = 25
    c.avg_hr = 128
    c.calories_burned_estimate = 180
    c.notes = "Treadmill 12% incline"
    c.created_at = now
    return c


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


class TestListSessions:
    async def test_no_auth_returns_401(self, client):
        resp = await client.get(f"/preps/{_PREP_ID}/sessions")
        assert resp.status_code == 401

    async def test_prep_not_found_returns_404(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=None)):
            resp = await client.get(f"/preps/{_PREP_ID}/sessions", headers=_auth())
        assert resp.status_code == 404

    async def test_returns_list(self, client):
        session = _mock_session()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.session_service.list_sessions", new=AsyncMock(return_value=[session])):
                resp = await client.get(f"/preps/{_PREP_ID}/sessions", headers=_auth())
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 1


class TestCreateSession:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(
            f"/preps/{_PREP_ID}/sessions",
            json={"started_at": "2026-05-04T07:30:00Z"},
        )
        assert resp.status_code == 401

    async def test_creates_session(self, client):
        session = _mock_session()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.session_service.create_session", new=AsyncMock(return_value=session)):
                resp = await client.post(
                    f"/preps/{_PREP_ID}/sessions",
                    json={"started_at": "2026-05-04T07:30:00Z", "title": "Chest Day"},
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Chest Day"

    async def test_missing_started_at_returns_422(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            resp = await client.post(
                f"/preps/{_PREP_ID}/sessions",
                json={},
                headers=_auth(),
            )
        assert resp.status_code == 422


class TestPatchSession:
    async def test_not_found_returns_404(self, client):
        with patch("app.services.session_service.get_session", new=AsyncMock(return_value=None)):
            resp = await client.patch(
                f"/sessions/{_SESSION_ID}",
                json={"notes": "good session"},
                headers=_auth(),
            )
        assert resp.status_code == 404

    async def test_patch_notes(self, client):
        session = _mock_session()
        patched = _mock_session()
        patched.notes = "great session"
        with patch("app.services.session_service.get_session", new=AsyncMock(return_value=session)):
            with patch("app.services.session_service.patch_session", new=AsyncMock(return_value=patched)):
                resp = await client.patch(
                    f"/sessions/{_SESSION_ID}",
                    json={"notes": "great session"},
                    headers=_auth(),
                )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "great session"


class TestCreateSet:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(
            f"/sessions/{_SESSION_ID}/sets",
            json={"exercise_name_raw": "Bench Press", "weight_kg": 80, "reps": 8},
        )
        assert resp.status_code == 401

    async def test_creates_set(self, client):
        session = _mock_session()
        set_log = _mock_set_log()
        with patch("app.services.session_service.get_session", new=AsyncMock(return_value=session)):
            with patch("app.services.session_service.create_set", new=AsyncMock(return_value=set_log)):
                resp = await client.post(
                    f"/sessions/{_SESSION_ID}/sets",
                    json={"exercise_name_raw": "Incline DB Press", "weight_kg": 30, "reps": 8, "set_number": 1},
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["exercise_name_raw"] == "Incline DB Press"
        assert resp.json()["canonical_exercise_id"] == str(_CANONICAL_ID)

    async def test_session_not_found_returns_404(self, client):
        with patch("app.services.session_service.get_session", new=AsyncMock(return_value=None)):
            resp = await client.post(
                f"/sessions/{_SESSION_ID}/sets",
                json={"exercise_name_raw": "Bench", "weight_kg": 80, "reps": 8},
                headers=_auth(),
            )
        assert resp.status_code == 404


class TestDeleteSet:
    async def test_no_auth_returns_401(self, client):
        set_id = uuid.uuid4()
        resp = await client.delete(f"/sets/{set_id}")
        assert resp.status_code == 401

    async def test_not_found_returns_404(self, client):
        with patch("app.services.session_service.get_set", new=AsyncMock(return_value=None)):
            resp = await client.delete(f"/sets/{uuid.uuid4()}", headers=_auth())
        assert resp.status_code == 404

    async def test_deletes_set(self, client):
        set_log = _mock_set_log()
        with patch("app.services.session_service.get_set", new=AsyncMock(return_value=set_log)):
            with patch("app.services.session_service.delete_set", new=AsyncMock(return_value=None)):
                resp = await client.delete(f"/sets/{set_log.id}", headers=_auth())
        assert resp.status_code == 204


class TestExerciseHistory:
    async def test_no_auth_returns_401(self, client):
        resp = await client.get(f"/exercises/by-canonical/{_CANONICAL_ID}/history")
        assert resp.status_code == 401

    async def test_returns_history(self, client):
        from app.schemas.session import ExerciseHistoryResponse
        mock_history = ExerciseHistoryResponse(
            canonical_exercise_id=_CANONICAL_ID,
            canonical_name="Incline Dumbbell Bench Press",
            sessions=[],
            all_time_best=None,
        )
        with patch("app.services.session_service.get_exercise_history", new=AsyncMock(return_value=mock_history)):
            resp = await client.get(f"/exercises/by-canonical/{_CANONICAL_ID}/history", headers=_auth())
        assert resp.status_code == 200
        data = resp.json()
        assert data["canonical_exercise_id"] == str(_CANONICAL_ID)
        assert data["canonical_name"] == "Incline Dumbbell Bench Press"
        assert isinstance(data["sessions"], list)


class TestCardioLog:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(
            f"/preps/{_PREP_ID}/cardio-logs",
            json={"performed_at": "2026-05-04T18:00:00Z", "modality": "incline_walk", "duration_min": 25},
        )
        assert resp.status_code == 401

    async def test_creates_cardio_log(self, client):
        cardio = _mock_cardio_log()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.session_service.create_cardio_log", new=AsyncMock(return_value=cardio)):
                resp = await client.post(
                    f"/preps/{_PREP_ID}/cardio-logs",
                    json={
                        "performed_at": "2026-05-04T18:00:00Z",
                        "modality": "incline_walk",
                        "duration_min": 25,
                        "avg_hr": 128,
                    },
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["modality"] == "incline_walk"
        assert resp.json()["duration_min"] == 25

    async def test_prep_not_found_returns_404(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=None)):
            resp = await client.post(
                f"/preps/{_PREP_ID}/cardio-logs",
                json={"performed_at": "2026-05-04T18:00:00Z", "modality": "bike"},
                headers=_auth(),
            )
        assert resp.status_code == 404
