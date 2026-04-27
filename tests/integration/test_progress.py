"""Integration tests for progress endpoints: weights, measurements, check-ins, photos, reports."""
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
    p.starting_weight_kg = 84.5
    p.phase_split = {"maintenance_weeks": 4, "cut_weeks": 12}
    p.current_workout_template_id = None
    p.current_weekly_plan_id = None
    p.completion_notes = None
    p.created_at = now
    p.updated_at = now
    return p


def _mock_weight_log():
    now = datetime.now(timezone.utc)
    w = MagicMock()
    w.id = uuid.uuid4()
    w.user_id = uuid.UUID(_USER_ID)
    w.prep_id = _PREP_ID
    w.logged_at = now
    w.weight_kg = 84.5
    w.source = "manual"
    w.notes = None
    w.created_at = now
    return w


def _mock_measurement():
    now = datetime.now(timezone.utc)
    m = MagicMock()
    m.id = uuid.uuid4()
    m.user_id = uuid.UUID(_USER_ID)
    m.prep_id = _PREP_ID
    m.logged_at = now
    m.chest_cm = 102.0
    m.waist_cm = 82.0
    m.hips_cm = None
    m.left_arm_cm = None
    m.right_arm_cm = None
    m.left_thigh_cm = None
    m.right_thigh_cm = None
    m.left_calf_cm = None
    m.right_calf_cm = None
    m.notes = None
    m.created_at = now
    return m


def _mock_photo():
    now = datetime.now(timezone.utc)
    p = MagicMock()
    p.id = uuid.uuid4()
    p.user_id = uuid.UUID(_USER_ID)
    p.prep_id = _PREP_ID
    p.storage_key = "users/abc/preps/xyz/photos/123.jpg"
    p.thumbnail_key = None
    p.taken_at = now
    p.week_number = 1
    p.angle = "front"
    p.body_part = None
    p.created_at = now
    p.url = None
    p.thumbnail_url = None
    return p


def _mock_check_in():
    now = datetime.now(timezone.utc)
    c = MagicMock()
    c.id = uuid.uuid4()
    c.user_id = uuid.UUID(_USER_ID)
    c.prep_id = _PREP_ID
    c.week_number = 1
    c.completed_at = now
    c.weight_kg = 84.2
    c.mood = 4
    c.energy = 4
    c.sleep = 3
    c.training_quality = 4
    c.notes = "Good week"
    c.measurement_log_id = None
    c.created_at = now
    return c


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


class TestWeightLog:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(f"/preps/{_PREP_ID}/weights", json={"weight_kg": 84.5})
        assert resp.status_code == 401

    async def test_creates_weight_log(self, client):
        weight = _mock_weight_log()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.progress_service.log_weight", new=AsyncMock(return_value=weight)):
                resp = await client.post(
                    f"/preps/{_PREP_ID}/weights",
                    json={"weight_kg": 84.5},
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["weight_kg"] == 84.5

    async def test_list_weights_returns_trend(self, client):
        from app.schemas.progress import WeightTrend
        weights = [_mock_weight_log()]
        trend = WeightTrend(current_avg_7d=84.5, previous_avg_7d=None, delta_kg=None, trajectory="insufficient_data")
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.progress_service.list_weights", new=AsyncMock(return_value=weights)):
                with patch("app.services.progress_service.compute_trend", return_value=trend):
                    resp = await client.get(f"/preps/{_PREP_ID}/weights", headers=_auth())
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "trend" in data
        assert data["trend"]["trajectory"] == "insufficient_data"


class TestMeasurementLog:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(f"/preps/{_PREP_ID}/measurements", json={"chest_cm": 102})
        assert resp.status_code == 401

    async def test_creates_measurement(self, client):
        measurement = _mock_measurement()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.progress_service.log_measurement", new=AsyncMock(return_value=measurement)):
                resp = await client.post(
                    f"/preps/{_PREP_ID}/measurements",
                    json={"chest_cm": 102.0, "waist_cm": 82.0},
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["chest_cm"] == 102.0


class TestPhotoEndpoints:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(
            f"/preps/{_PREP_ID}/photos",
            json={"storage_key": "test.jpg", "taken_at": "2026-05-04T09:00:00Z"},
        )
        assert resp.status_code == 401

    async def test_registers_photo(self, client):
        photo = _mock_photo()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.progress_service.register_photo", new=AsyncMock(return_value=photo)):
                resp = await client.post(
                    f"/preps/{_PREP_ID}/photos",
                    json={"storage_key": "test.jpg", "taken_at": "2026-05-04T09:00:00Z", "week_number": 1},
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["week_number"] == 1

    async def test_delete_photo_not_found(self, client):
        with patch("app.services.progress_service.get_photo", new=AsyncMock(return_value=None)):
            resp = await client.delete(f"/photos/{uuid.uuid4()}", headers=_auth())
        assert resp.status_code == 404


class TestCheckIn:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(
            f"/preps/{_PREP_ID}/check-ins",
            json={"week_number": 1, "completed_at": "2026-05-11T09:00:00Z"},
        )
        assert resp.status_code == 401

    async def test_creates_check_in(self, client):
        check_in = _mock_check_in()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.progress_service.create_check_in", new=AsyncMock(return_value=check_in)):
                resp = await client.post(
                    f"/preps/{_PREP_ID}/check-ins",
                    json={"week_number": 1, "completed_at": "2026-05-11T09:00:00Z", "weight_kg": 84.2, "mood": 4},
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["week_number"] == 1
        assert resp.json()["mood"] == 4

    async def test_get_check_in_not_found(self, client):
        with patch("app.services.progress_service.get_check_in", new=AsyncMock(return_value=None)):
            resp = await client.get(f"/check-ins/{uuid.uuid4()}", headers=_auth())
        assert resp.status_code == 404

    async def test_list_check_ins(self, client):
        check_in = _mock_check_in()
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.progress_service.list_check_ins", new=AsyncMock(return_value=[check_in])):
                resp = await client.get(f"/preps/{_PREP_ID}/check-ins", headers=_auth())
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestReports:
    async def test_list_reports_no_auth(self, client):
        resp = await client.get(f"/preps/{_PREP_ID}/reports")
        assert resp.status_code == 401

    async def test_get_report_not_found(self, client):
        with patch("app.services.progress_service.get_report_by_id", new=AsyncMock(return_value=None)):
            resp = await client.get(f"/reports/{uuid.uuid4()}", headers=_auth())
        assert resp.status_code == 404
