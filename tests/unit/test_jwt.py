"""Unit tests for JWT verification in app/auth/supabase_jwt.py."""
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

TEST_SECRET = "test-jwt-secret-must-be-at-least-32-chars-long!"
TEST_USER_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_token(
    secret: str = TEST_SECRET,
    sub: str = TEST_USER_ID,
    email: str = "ebuka@example.com",
    role: str = "authenticated",
    aud: str = "authenticated",
    exp_offset: int = 3600,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "aud": aud,
        "iat": now,
        "exp": now + exp_offset,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_SECRET)
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_valid_token_returns_auth_user():
    from app.auth.supabase_jwt import get_current_user

    token = _make_token()
    credentials = _make_credentials(token)
    user = await get_current_user(credentials)

    assert user.id == TEST_USER_ID
    assert user.email == "ebuka@example.com"
    assert user.role == "authenticated"


async def test_expired_token_raises_401():
    from app.auth.supabase_jwt import get_current_user

    token = _make_token(exp_offset=-1)  # already expired
    credentials = _make_credentials(token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "auth_expired"


async def test_wrong_signature_raises_401():
    from app.auth.supabase_jwt import get_current_user

    token = _make_token(secret="wrong-secret-that-does-not-match-the-configured-one")
    credentials = _make_credentials(token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "auth_invalid"


async def test_malformed_token_raises_401():
    from app.auth.supabase_jwt import get_current_user

    credentials = _make_credentials("not.a.valid.jwt.at.all")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "auth_invalid"


async def test_token_missing_sub_raises_401():
    from app.auth.supabase_jwt import get_current_user

    now = int(time.time())
    # Token with no 'sub' claim
    payload = {"email": "ebuka@example.com", "aud": "authenticated", "iat": now, "exp": now + 3600}
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
    credentials = _make_credentials(token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "auth_invalid"


async def test_wrong_audience_raises_401():
    from app.auth.supabase_jwt import get_current_user

    token = _make_token(aud="wrong_audience")
    credentials = _make_credentials(token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == 401
