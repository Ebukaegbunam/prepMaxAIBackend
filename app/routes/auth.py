"""Auth routes — Google OAuth via Supabase."""
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.schemas.auth import AppleCallbackRequest, AuthResponse, AuthStartResponse, GoogleCallbackRequest, RefreshRequest, SessionResponse, SessionUser

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger()


def _oauth_start_url(settings, provider: str, code_challenge: str = "", code_challenge_method: str = "S256") -> str:
    params: dict[str, str] = {
        "provider": provider,
        "redirect_to": "prepmax://auth/callback",
        "access_type": "offline",
        "scopes": "email profile",
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = code_challenge_method
    return f"{settings.SUPABASE_URL}/auth/v1/authorize?{urlencode(params)}"


@router.get("/google/start", response_model=AuthStartResponse)
async def google_start(code_challenge: str = "", code_challenge_method: str = "S256") -> AuthStartResponse:
    settings = get_settings()
    return AuthStartResponse(auth_url=_oauth_start_url(settings, "google", code_challenge, code_challenge_method))


@router.get("/apple/start", response_model=AuthStartResponse)
async def apple_start() -> AuthStartResponse:
    settings = get_settings()
    return AuthStartResponse(auth_url=_oauth_start_url(settings, "apple"))


@router.post("/google/callback", response_model=AuthResponse)
async def google_callback(body: GoogleCallbackRequest) -> AuthResponse:
    settings = get_settings()

    # Exchange code + PKCE verifier for session with Supabase
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=pkce",
            json={"auth_code": body.code, "code_verifier": body.code_verifier},
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth_invalid", "message": "OAuth code exchange failed"}},
        )

    data = resp.json()
    user_data = data.get("user", {})
    user_meta = user_data.get("user_metadata", {}) or {}
    exp_ts = data.get("expires_at") or data.get("expires_in", 3600)

    if isinstance(exp_ts, int) and exp_ts < 9999999999:
        # It's a relative seconds value
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=exp_ts)
    else:
        expires_at = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)

    return AuthResponse(
        user=SessionUser(
            id=user_data.get("id", ""),
            email=user_data.get("email"),
            name=user_meta.get("full_name") or user_meta.get("name"),
        ),
        session=SessionResponse(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=expires_at,
        ),
    )


@router.post("/apple/callback", response_model=AuthResponse)
async def apple_callback(body: AppleCallbackRequest) -> AuthResponse:
    """Exchange a native Apple identityToken (from expo-apple-authentication) for a Supabase session."""
    settings = get_settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=id_token",
            json={
                "provider": "apple",
                "id_token": body.identity_token,
                "nonce": body.nonce,
            },
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth_invalid", "message": "Apple identity token invalid or expired"}},
        )

    data = resp.json()
    user_data = data.get("user", {})
    user_meta = user_data.get("user_metadata", {}) or {}
    exp_ts = data.get("expires_at") or data.get("expires_in", 3600)

    if isinstance(exp_ts, int) and exp_ts < 9_999_999_999:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=exp_ts)
    else:
        expires_at = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)

    return AuthResponse(
        user=SessionUser(
            id=user_data.get("id", ""),
            email=user_data.get("email"),
            name=user_meta.get("full_name") or user_meta.get("name"),
        ),
        session=SessionResponse(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=expires_at,
        ),
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(body: RefreshRequest) -> AuthResponse:
    settings = get_settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": body.refresh_token},
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth_expired", "message": "Refresh token invalid or expired"}},
        )

    data = resp.json()
    user_data = data.get("user", {})
    user_meta = user_data.get("user_metadata", {}) or {}
    expires_at = datetime.fromtimestamp(int(data.get("expires_at", 0)), tz=timezone.utc)

    return AuthResponse(
        user=SessionUser(
            id=user_data.get("id", ""),
            email=user_data.get("email"),
            name=user_meta.get("full_name") or user_meta.get("name"),
        ),
        session=SessionResponse(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=expires_at,
        ),
    )


@router.post("/sign-out", status_code=204)
async def sign_out() -> None:
    # Token revocation happens client-side via Supabase SDK.
    # Server just returns 204 — the client discards its local tokens.
    pass
