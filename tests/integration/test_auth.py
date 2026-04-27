"""Integration tests for /auth endpoints — Supabase HTTP calls are mocked."""
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

_SECRET = "test-jwt-secret-must-be-at-least-32-chars-long!"


def _make_token(user_id: str | None = None, exp_offset: int = 3600) -> str:
    payload = {
        "sub": user_id or str(uuid.uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "exp": int(time.time()) + exp_offset,
    }
    return jwt.encode(payload, _SECRET, algorithm="HS256")


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


pytestmark = pytest.mark.anyio


class TestGoogleStart:
    async def test_returns_auth_url(self, client):
        resp = await client.get("/auth/google/start")
        assert resp.status_code == 200
        data = resp.json()
        assert "auth_url" in data

    async def test_url_contains_google_provider(self, client):
        resp = await client.get("/auth/google/start")
        assert resp.status_code == 200
        assert "provider=google" in resp.json()["auth_url"]

    async def test_url_points_to_supabase(self, client):
        resp = await client.get("/auth/google/start")
        assert resp.status_code == 200
        assert "test.supabase.co" in resp.json()["auth_url"]


class TestGoogleCallback:
    async def test_missing_code_returns_422(self, client):
        resp = await client.post("/auth/google/callback", json={})
        assert resp.status_code == 422

    async def test_successful_callback_returns_tokens(self, client):
        user_id = str(uuid.uuid4())
        access_token = _make_token(user_id)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": access_token,
            "refresh_token": "rt-test",
            "expires_in": 3600,
            "token_type": "bearer",
            "user": {"id": user_id, "email": "test@example.com", "user_metadata": {}},
        }

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            resp = await client.post(
                "/auth/google/callback",
                json={"code": "test-auth-code"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert data["session"]["access_token"] == access_token

    async def test_supabase_error_returns_401(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "invalid_grant"}

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            resp = await client.post(
                "/auth/google/callback",
                json={"code": "invalid-code", "code_verifier": "bad-verifier"},
            )

        assert resp.status_code == 401

    async def test_callback_with_code_verifier(self, client):
        user_id = str(uuid.uuid4())
        access_token = _make_token(user_id)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": access_token,
            "refresh_token": "rt-test",
            "expires_in": 3600,
            "token_type": "bearer",
            "user": {"id": user_id, "email": "test@example.com", "user_metadata": {}},
        }

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            resp = await client.post(
                "/auth/google/callback",
                json={"code": "pkce-auth-code", "code_verifier": "the-verifier"},
            )

        assert resp.status_code == 200
        # Verify code_verifier was forwarded to Supabase
        call_json = mock_http.post.call_args.kwargs.get("json") or mock_http.post.call_args.args[1] if mock_http.post.call_args.args[1:] else mock_http.post.call_args[1].get("json", {})
        assert call_json.get("code_verifier") == "the-verifier"


class TestRefresh:
    async def test_missing_token_returns_422(self, client):
        resp = await client.post("/auth/refresh", json={})
        assert resp.status_code == 422

    async def test_successful_refresh(self, client):
        user_id = str(uuid.uuid4())
        new_token = _make_token(user_id)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": new_token,
            "refresh_token": "rt-new",
            "expires_at": int(time.time()) + 3600,
            "user": {"id": user_id, "email": "test@example.com", "user_metadata": {}},
        }

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            resp = await client.post(
                "/auth/refresh",
                json={"refresh_token": "old-refresh-token"},
            )

        assert resp.status_code == 200
        assert resp.json()["session"]["access_token"] == new_token

    async def test_invalid_refresh_token_returns_401(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "invalid_grant"}

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            resp = await client.post(
                "/auth/refresh",
                json={"refresh_token": "expired-token"},
            )

        assert resp.status_code == 401


class TestSignOut:
    async def test_sign_out_returns_204(self, client):
        resp = await client.post("/auth/sign-out")
        assert resp.status_code == 204
