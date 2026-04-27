"""Integration tests for /competitions and /users/me/saved-competitions endpoints."""
import time
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

_SECRET = "test-jwt-secret-must-be-at-least-32-chars-long!"
_USER_ID = str(uuid.uuid4())
_COMP_ID = uuid.uuid4()
_SAVED_ID = uuid.uuid4()


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


def _mock_competition(comp_id: uuid.UUID = _COMP_ID) -> MagicMock:
    now = datetime.now(timezone.utc)
    c = MagicMock()
    c.id = comp_id
    c.name = "NPC Bay Area Classic"
    c.date = date(2026, 8, 24)
    c.federation = "NPC"
    c.tested = False
    c.city = "Oakland"
    c.state = "CA"
    c.country = "US"
    c.lat = 37.8044
    c.lng = -122.2712
    c.divisions = ["classic_physique", "mens_physique"]
    c.registration_url = "https://npcnewsonline.com/events"
    c.refreshed_at = now
    c.created_at = now
    return c


def _mock_saved(saved_id: uuid.UUID = _SAVED_ID, comp_id: uuid.UUID = _COMP_ID) -> MagicMock:
    now = datetime.now(timezone.utc)
    s = MagicMock()
    s.id = saved_id
    s.competition_id = comp_id
    s.snapshot = {
        "name": "NPC Bay Area Classic",
        "date": "2026-08-24",
        "federation": "NPC",
        "tested": False,
        "city": "Oakland",
        "state": "CA",
        "country": "US",
        "divisions": ["classic_physique", "mens_physique"],
        "registration_url": "https://npcnewsonline.com/events",
    }
    s.created_at = now
    return s


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        import httpx
        transport = ASGITransport(app=application)
        with httpx.Client() as _:
            import asyncio

        async def _make() -> AsyncClient:
            return AsyncClient(transport=transport, base_url="http://test")

        return asyncio.get_event_loop().run_until_complete(_make())


@pytest.fixture
def async_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")
    return monkeypatch


@pytest.mark.anyio
async def test_search_competitions_returns_results(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    comp = _mock_competition()

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.search_competitions", AsyncMock(return_value=([comp], "fresh"))):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/competitions/search", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert body["cache_status"] == "fresh"
    assert len(body["results"]) == 1
    assert body["results"][0]["name"] == "NPC Bay Area Classic"
    assert body["results"][0]["federation"] == "NPC"
    assert "cached_until" in body


@pytest.mark.anyio
async def test_search_competitions_stale_cache(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    comp = _mock_competition()

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.search_competitions", AsyncMock(return_value=([comp], "stale"))):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/competitions/search", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["cache_status"] == "stale"


@pytest.mark.anyio
async def test_search_competitions_with_filters(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.search_competitions", AsyncMock(return_value=([], "fresh"))) as mock_search:
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get(
                "/competitions/search",
                params={"division": "classic_physique", "tested": "false", "federation": "NPC"},
                headers=_auth(),
            )

    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.anyio
async def test_get_competition_found(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    comp = _mock_competition()

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.get_competition", AsyncMock(return_value=comp)):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get(f"/competitions/{_COMP_ID}", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["id"] == str(_COMP_ID)
    assert resp.json()["name"] == "NPC Bay Area Classic"


@pytest.mark.anyio
async def test_get_competition_not_found(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.get_competition", AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get(f"/competitions/{uuid.uuid4()}", headers=_auth())

    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_save_competition_success(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    saved = _mock_saved()

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.save_competition", AsyncMock(return_value=saved)):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.post(
                "/users/me/saved-competitions",
                json={"competition_id": str(_COMP_ID)},
                headers=_auth(),
            )

    assert resp.status_code == 201
    body = resp.json()
    assert body["competition_id"] == str(_COMP_ID)
    assert body["snapshot"]["name"] == "NPC Bay Area Classic"
    assert body["snapshot"]["federation"] == "NPC"


@pytest.mark.anyio
async def test_save_competition_not_found(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.save_competition", AsyncMock(side_effect=ValueError("Competition not found"))):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.post(
                "/users/me/saved-competitions",
                json={"competition_id": str(uuid.uuid4())},
                headers=_auth(),
            )

    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_list_saved_competitions(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    saved = _mock_saved()

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.list_saved_competitions", AsyncMock(return_value=[saved])):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/users/me/saved-competitions", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["competition_id"] == str(_COMP_ID)


@pytest.mark.anyio
async def test_list_saved_competitions_empty(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.list_saved_competitions", AsyncMock(return_value=[])):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.get("/users/me/saved-competitions", headers=_auth())

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_delete_saved_competition_success(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.delete_saved_competition", AsyncMock(return_value=True)):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.delete(f"/users/me/saved-competitions/{_COMP_ID}", headers=_auth())

    assert resp.status_code == 204


@pytest.mark.anyio
async def test_delete_saved_competition_not_found(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory), \
         patch("app.services.competition_service.delete_saved_competition", AsyncMock(return_value=False)):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            resp = await ac.delete(f"/users/me/saved-competitions/{uuid.uuid4()}", headers=_auth())

    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_competition_endpoints_require_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.setenv("APP_ENV", "test")

    from app.main import create_app
    application = create_app()

    mock_factory, mock_db = _make_db_mock()

    async def _get_db_override():
        yield mock_db

    from app.db.session import get_db
    application.dependency_overrides[get_db] = _get_db_override

    with patch("app.db.session.AsyncSessionLocal", mock_factory):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
            r1 = await ac.get("/competitions/search")
            r2 = await ac.get(f"/competitions/{_COMP_ID}")
            r3 = await ac.get("/users/me/saved-competitions")
            r4 = await ac.post("/users/me/saved-competitions", json={"competition_id": str(_COMP_ID)})
            r5 = await ac.delete(f"/users/me/saved-competitions/{_COMP_ID}")

    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r3.status_code == 401
    assert r4.status_code == 401
    assert r5.status_code == 401
