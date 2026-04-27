"""Auth routes — Google OAuth via Supabase."""
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.schemas.auth import AuthResponse, AuthStartResponse, GoogleCallbackRequest, RefreshRequest, SessionResponse, SessionUser

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger()


@router.get("/google/start", response_model=AuthStartResponse)
async def google_start() -> AuthStartResponse:
    settings = get_settings()
    params = {
        "provider": "google",
        "redirect_to": "prepai://auth/callback",
        "access_type": "offline",
        "scopes": "email profile",
    }
    auth_url = f"{settings.SUPABASE_URL}/auth/v1/authorize?{urlencode(params)}"
    return AuthStartResponse(auth_url=auth_url)


@router.post("/google/callback", response_model=AuthResponse)
async def google_callback(body: GoogleCallbackRequest) -> AuthResponse:
    settings = get_settings()

    # Exchange code for session with Supabase
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=pkce",
            json={"auth_code": body.code},
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
        )

    if resp.status_code != 200:
        # Treat code as a direct access_token if exchange fails (client-side PKCE)
        from app.auth.supabase_jwt import _decode_token
        try:
            payload = _decode_token(body.code, settings.SUPABASE_JWT_SECRET)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "auth_invalid", "message": "Invalid OAuth code or token"}},
            )
        user_id = payload.get("sub", "")
        email = payload.get("email")
        exp = payload.get("exp", 0)
        return AuthResponse(
            user=SessionUser(id=user_id, email=email, name=payload.get("user_metadata", {}).get("full_name") if isinstance(payload.get("user_metadata"), dict) else None),
            session=SessionResponse(
                access_token=body.code,
                refresh_token="",
                expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
            ),
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
