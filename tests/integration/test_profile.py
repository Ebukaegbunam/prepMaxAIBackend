"""Integration tests for /profile endpoints — all DB and LLM calls are mocked."""
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

_SECRET = "test-jwt-secret-must-be-at-least-32-chars-long!"
_USER_ID = str(uuid.uuid4())


def _make_token(user_id: str = _USER_ID, exp_offset: int = 3600) -> str:
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "exp": int(time.time()) + exp_offset,
    }
    return jwt.encode(payload, _SECRET, algorithm="HS256")


def _auth_headers(user_id: str = _USER_ID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _expired_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(exp_offset=-3600)}"}


def _mock_profile(user_id: str = _USER_ID) -> MagicMock:
    now = datetime.now(timezone.utc)
    p = MagicMock()
    p.id = uuid.uuid4()
    p.user_id = uuid.UUID(user_id)
    p.name = "Test User"
    p.age = 25
    p.sex = "male"
    p.height_cm = 180.0
    p.units_weight = "lb"
    p.units_measurement = "in"
    p.dietary_restrictions = []
    p.loved_foods = []
    p.hated_foods = []
    p.cooking_skill = None
    p.kitchen_equipment = []
    p.job_type = None
    p.work_hours = None
    p.stress_level = None
    p.sleep_window = None
    p.preferred_training_time = None
    p.training_days_per_week = None
    p.narrative = "Test User is a 25-year-old male bodybuilder."
    p.narrative_updated_at = now
    p.created_at = now
    p.updated_at = now
    return p


def _make_db_mock() -> tuple[MagicMock, MagicMock]:
    """Return (session_factory_mock, db_session_mock).

    The factory mock can be used to patch AsyncSessionLocal.
    The db mock is yielded by get_db dependency override.
    """
    # scalar() must return a plain int, not a coroutine — use MagicMock, not AsyncMock
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.flush = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_cm)

    return mock_factory, mock_db


@pytest.fixture
def app():
    import os
    os.environ["APP_ENV"] = "test"
    os.environ["SUPABASE_JWT_SECRET"] = _SECRET
    os.environ["SUPABASE_URL"] = "https://test.supabase.co"
    os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"
    os.environ["OPENAI_API_KEY"] = "sk-test"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:test@localhost/test"

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


class TestGetProfile:
    async def test_no_auth_returns_401(self, client):
        resp = await client.get("/profile")
        assert resp.status_code == 401

    async def test_expired_token_returns_401(self, client):
        resp = await client.get("/profile", headers=_expired_headers())
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"]["code"] == "auth_expired"

    async def test_profile_not_found_returns_404(self, client):
        with patch("app.services.profile_service.get_profile", new=AsyncMock(return_value=None)):
            resp = await client.get("/profile", headers=_auth_headers())
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "not_found"

    async def test_returns_profile_when_found(self, client):
        profile = _mock_profile()
        with patch("app.services.profile_service.get_profile", new=AsyncMock(return_value=profile)):
            resp = await client.get("/profile", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test User"
        assert data["narrative"] == "Test User is a 25-year-old male bodybuilder."

    async def test_response_has_expected_fields(self, client):
        profile = _mock_profile()
        with patch("app.services.profile_service.get_profile", new=AsyncMock(return_value=profile)):
            resp = await client.get("/profile", headers=_auth_headers())
        data = resp.json()
        for field in ("id", "user_id", "name", "created_at", "updated_at"):
            assert field in data, f"Missing field: {field}"


class TestInitializeProfile:
    async def test_no_auth_returns_401(self, client):
        resp = await client.post("/profile/initialize", json={"name": "Alex"})
        assert resp.status_code == 401

    async def test_creates_profile_returns_201(self, client):
        profile = _mock_profile()
        with patch("app.services.profile_service.initialize_profile", new=AsyncMock(return_value=profile)):
            resp = await client.post(
                "/profile/initialize",
                json={"name": "Test User", "age": 25, "sex": "male"},
                headers=_auth_headers(),
            )
        assert resp.status_code == 201

    async def test_narrative_returned_on_create(self, client):
        profile = _mock_profile()
        with patch("app.services.profile_service.initialize_profile", new=AsyncMock(return_value=profile)):
            resp = await client.post(
                "/profile/initialize",
                json={"name": "Test User"},
                headers=_auth_headers(),
            )
        assert resp.json()["narrative"] is not None

    async def test_missing_name_returns_422(self, client):
        resp = await client.post(
            "/profile/initialize",
            json={"age": 25},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    async def test_invalid_sex_returns_422(self, client):
        resp = await client.post(
            "/profile/initialize",
            json={"name": "Alex", "sex": "robot"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    async def test_training_days_out_of_range_returns_422(self, client):
        resp = await client.post(
            "/profile/initialize",
            json={"name": "Alex", "training_days_per_week": 10},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    async def test_service_error_returns_500(self, client):
        with patch(
            "app.services.profile_service.initialize_profile",
            new=AsyncMock(side_effect=RuntimeError("DB failure")),
        ):
            resp = await client.post(
                "/profile/initialize",
                json={"name": "Alex"},
                headers=_auth_headers(),
            )
        assert resp.status_code == 500


class TestPatchProfile:
    async def test_no_auth_returns_401(self, client):
        resp = await client.patch("/profile", json={"name": "New"})
        assert resp.status_code == 401

    async def test_empty_body_returns_400(self, client):
        resp = await client.patch("/profile", json={}, headers=_auth_headers())
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"]["code"] == "validation_error"

    async def test_patches_name(self, client):
        updated = _mock_profile()
        updated.name = "Updated Name"
        with patch("app.services.profile_service.patch_profile", new=AsyncMock(return_value=updated)):
            resp = await client.patch(
                "/profile",
                json={"name": "Updated Name"},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    async def test_patch_on_missing_profile_returns_404(self, client):
        with patch(
            "app.services.profile_service.patch_profile",
            new=AsyncMock(side_effect=ValueError("Profile not found")),
        ):
            resp = await client.patch(
                "/profile",
                json={"name": "X"},
                headers=_auth_headers(),
            )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "not_found"

    async def test_invalid_stress_level_returns_422(self, client):
        resp = await client.patch(
            "/profile",
            json={"stress_level": "extreme"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    async def test_partial_update_only_sends_provided_fields(self, client):
        updated = _mock_profile()
        updated.age = 30
        mock_patch = AsyncMock(return_value=updated)
        with patch("app.services.profile_service.patch_profile", new=mock_patch):
            await client.patch(
                "/profile",
                json={"age": 30},
                headers=_auth_headers(),
            )
        # Verify service was called with only the provided field
        call_kwargs = mock_patch.call_args.kwargs
        assert "age" in call_kwargs["updates"]
        assert "name" not in call_kwargs["updates"]
