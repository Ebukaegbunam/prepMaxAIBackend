"""Integration tests for meal plan, meal log, and weekly plan endpoints."""
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
_MEAL_PLAN_ID = uuid.uuid4()
_MEAL_LOG_ID = uuid.uuid4()
_WEEKLY_PLAN_ID = uuid.uuid4()


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
    p.target_weight_kg = 78.0
    p.phase_split = {"maintenance_weeks": 4, "cut_weeks": 12}
    p.current_workout_template_id = None
    p.current_weekly_plan_id = None
    p.completion_notes = None
    p.created_at = now
    p.updated_at = now
    return p


def _mock_weekly_plan():
    now = datetime.now(timezone.utc)
    w = MagicMock()
    w.id = _WEEKLY_PLAN_ID
    w.user_id = uuid.UUID(_USER_ID)
    w.prep_id = _PREP_ID
    w.week_number = 1
    w.targets = {"calories": 2950, "protein_g": 186, "carbs_g": 325, "fat_g": 76}
    w.created_at = now
    w.updated_at = now
    return w


def _mock_meal_plan():
    now = datetime.now(timezone.utc)
    m = MagicMock()
    m.id = _MEAL_PLAN_ID
    m.user_id = uuid.UUID(_USER_ID)
    m.prep_id = _PREP_ID
    m.weekly_plan_id = _WEEKLY_PLAN_ID
    m.week_number = 1
    m.day_of_week = 1
    m.targets = {"calories": 2950, "protein_g": 186, "carbs_g": 325, "fat_g": 76}
    m.slots = []
    m.created_at = now
    m.updated_at = now
    return m


def _mock_meal_log():
    now = datetime.now(timezone.utc)
    log = MagicMock()
    log.id = _MEAL_LOG_ID
    log.user_id = uuid.UUID(_USER_ID)
    log.prep_id = _PREP_ID
    log.eaten_at = now
    log.slot = "breakfast"
    log.name = "Egg + Oats"
    log.calories = 620.0
    log.protein_g = 45.0
    log.carbs_g = 70.0
    log.fat_g = 18.0
    log.source = "planned"
    log.linked_meal_plan_id = None
    log.notes = None
    log.created_at = now
    return log


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


class TestGenerateWeeklyPlan:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(f"/preps/{_PREP_ID}/weekly-plans/generate")
        assert resp.status_code == 401

    async def test_prep_not_found_returns_404(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=None)):
            resp = await client.post(f"/preps/{_PREP_ID}/weekly-plans/generate", headers=_auth())
        assert resp.status_code == 404

    async def test_returns_week_targets(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.meal_service.generate_weekly_plan", new=AsyncMock(
                return_value=[{"week_number": w, "phase": "maintenance" if w <= 4 else "cut", "targets": {"calories": 2950, "protein_g": 186, "carbs_g": 325, "fat_g": 76}} for w in range(1, 17)]
            )):
                resp = await client.post(f"/preps/{_PREP_ID}/weekly-plans/generate", headers=_auth())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 16
        assert data[0]["week_number"] == 1
        assert data[0]["phase"] == "maintenance"
        assert data[4]["phase"] == "cut"


class TestWeeklyPlanCRUD:
    async def test_list_weekly_plans_no_auth(self, client):
        resp = await client.get(f"/preps/{_PREP_ID}/weekly-plans")
        assert resp.status_code == 401

    async def test_list_weekly_plans(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.meal_service.list_weekly_plans", new=AsyncMock(return_value=[_mock_weekly_plan()])):
                resp = await client.get(f"/preps/{_PREP_ID}/weekly-plans", headers=_auth())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_get_weekly_plan_not_found(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.meal_service.get_weekly_plan", new=AsyncMock(return_value=None)):
                resp = await client.get(f"/preps/{_PREP_ID}/weekly-plans/1", headers=_auth())
        assert resp.status_code == 404


class TestMealPlanCRUD:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(
            f"/preps/{_PREP_ID}/meal-plans",
            json={"week_number": 1, "day_of_week": 1},
        )
        assert resp.status_code == 401

    async def test_creates_meal_plan(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.meal_service.create_meal_plan", new=AsyncMock(return_value=_mock_meal_plan())):
                resp = await client.post(
                    f"/preps/{_PREP_ID}/meal-plans",
                    json={"week_number": 1, "day_of_week": 1},
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["week_number"] == 1

    async def test_patch_meal_plan(self, client):
        patched = _mock_meal_plan()
        patched.slots = [{"slot": "breakfast", "name": "Oats"}]
        with patch("app.services.meal_service.get_meal_plan", new=AsyncMock(return_value=_mock_meal_plan())):
            with patch("app.services.meal_service.patch_meal_plan", new=AsyncMock(return_value=patched)):
                resp = await client.patch(
                    f"/meal-plans/{_MEAL_PLAN_ID}",
                    json={"slots": [{"slot": "breakfast", "name": "Oats"}]},
                    headers=_auth(),
                )
        assert resp.status_code == 200


class TestMealLog:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post(
            f"/preps/{_PREP_ID}/meal-logs",
            json={"eaten_at": "2026-05-04T08:30:00Z", "name": "Eggs"},
        )
        assert resp.status_code == 401

    async def test_creates_meal_log(self, client):
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.meal_service.create_meal_log", new=AsyncMock(return_value=_mock_meal_log())):
                resp = await client.post(
                    f"/preps/{_PREP_ID}/meal-logs",
                    json={
                        "eaten_at": "2026-05-04T08:30:00Z",
                        "name": "Egg + Oats",
                        "calories": 620,
                        "protein_g": 45,
                        "slot": "breakfast",
                        "source": "planned",
                    },
                    headers=_auth(),
                )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Egg + Oats"

    async def test_delete_meal_log(self, client):
        with patch("app.services.meal_service.get_meal_log", new=AsyncMock(return_value=_mock_meal_log())):
            with patch("app.services.meal_service.delete_meal_log", new=AsyncMock(return_value=None)):
                resp = await client.delete(f"/meal-logs/{_MEAL_LOG_ID}", headers=_auth())
        assert resp.status_code == 204

    async def test_delete_not_found_returns_404(self, client):
        with patch("app.services.meal_service.get_meal_log", new=AsyncMock(return_value=None)):
            resp = await client.delete(f"/meal-logs/{_MEAL_LOG_ID}", headers=_auth())
        assert resp.status_code == 404

    async def test_get_daily_meal_logs(self, client):
        from app.schemas.meal import DailyMealLogResponse, MealLogResponse
        daily = DailyMealLogResponse(
            date="2026-05-04",
            totals={"calories": 620, "protein_g": 45, "carbs_g": 70, "fat_g": 18},
            targets={"calories": 2950, "protein_g": 186, "carbs_g": 325, "fat_g": 76},
            remaining={"calories": 2330, "protein_g": 141, "carbs_g": 255, "fat_g": 58},
            logs=[],
        )
        with patch("app.services.prep_service.get_prep", new=AsyncMock(return_value=_mock_prep())):
            with patch("app.services.meal_service.get_daily_meal_logs", new=AsyncMock(return_value=daily)):
                with patch("app.services.meal_service._get_profile", new=AsyncMock(return_value=None)):
                    resp = await client.get(
                        f"/preps/{_PREP_ID}/meal-logs?date=2026-05-04",
                        headers=_auth(),
                    )
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-05-04"
        assert "totals" in data
        assert "remaining" in data
