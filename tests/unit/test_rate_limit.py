"""Unit tests for rate limit helper functions."""
import uuid

import pytest
from jose import jwt

from app.middleware.rate_limit import _extract_user_id, _is_exempt

_SECRET = "test-jwt-secret-must-be-at-least-32-chars-long!"


def _make_token(user_id: str, audience: str = "authenticated") -> str:
    payload = {"sub": user_id, "aud": audience}
    return jwt.encode(payload, _SECRET, algorithm="HS256")


class TestIsExempt:
    def test_health_exempt(self):
        assert _is_exempt("/health") is True

    def test_ready_exempt(self):
        assert _is_exempt("/ready") is True

    def test_auth_prefix_exempt(self):
        assert _is_exempt("/auth/google/start") is True

    def test_test_prefix_exempt(self):
        assert _is_exempt("/__test__/profile/regenerate-narrative") is True

    def test_docs_exempt(self):
        assert _is_exempt("/__docs__") is True

    def test_openapi_exempt(self):
        assert _is_exempt("/openapi.json") is True

    def test_profile_not_exempt(self):
        assert _is_exempt("/profile") is False

    def test_root_not_exempt(self):
        assert _is_exempt("/") is False

    def test_api_not_exempt(self):
        assert _is_exempt("/api/something") is False


class TestExtractUserId:
    def test_valid_token(self):
        user_id = str(uuid.uuid4())
        token = _make_token(user_id)
        result = _extract_user_id(token, _SECRET)
        assert result == uuid.UUID(user_id)

    def test_invalid_token_returns_none(self):
        result = _extract_user_id("not.a.valid.token", _SECRET)
        assert result is None

    def test_wrong_secret_returns_none(self):
        user_id = str(uuid.uuid4())
        token = _make_token(user_id)
        result = _extract_user_id(token, "wrong-secret-that-is-also-at-least-32-chars!!")
        assert result is None

    def test_missing_sub_returns_none(self):
        payload = {"aud": "authenticated", "role": "user"}
        token = jwt.encode(payload, _SECRET, algorithm="HS256")
        result = _extract_user_id(token, _SECRET)
        assert result is None

    def test_invalid_uuid_sub_returns_none(self):
        payload = {"sub": "not-a-uuid", "aud": "authenticated"}
        token = jwt.encode(payload, _SECRET, algorithm="HS256")
        result = _extract_user_id(token, _SECRET)
        assert result is None

    def test_expired_token_still_extracts(self):
        # rate limiter uses verify_exp=False so expired tokens still count
        import time
        user_id = str(uuid.uuid4())
        payload = {"sub": user_id, "aud": "authenticated", "exp": int(time.time()) - 3600}
        token = jwt.encode(payload, _SECRET, algorithm="HS256")
        result = _extract_user_id(token, _SECRET)
        assert result == uuid.UUID(user_id)
