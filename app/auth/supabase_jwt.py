"""JWT verification — supports ES256 via Supabase JWKS and HS256 fallback."""
from typing import Annotated

import httpx
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

_bearer = HTTPBearer()
log = structlog.get_logger()

_jwks_cache: list[dict] = []


async def _load_jwks() -> list[dict]:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json",
                headers={"apikey": settings.SUPABASE_ANON_KEY},
            )
            if resp.status_code == 200:
                _jwks_cache = resp.json().get("keys", [])
                log.info("jwks_loaded", key_count=len(_jwks_cache))
    except Exception as exc:
        log.warning("jwks_load_failed", error=str(exc))
    return _jwks_cache


def _decode_with_keys(token: str, jwks: list[dict], jwt_secret: str) -> dict:
    # Try each JWKS public key (ES256 / RS256)
    for key in jwks:
        try:
            return jwt.decode(
                token, key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                options={"verify_exp": True},
            )
        except ExpiredSignatureError:
            raise
        except JWTError:
            continue

    # Fall back to HS256 symmetric secret
    if jwt_secret:
        return jwt.decode(
            token, jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )

    raise JWTError("No valid signing key matched the token")


class AuthUser(BaseModel):
    id: str
    email: str | None = None
    role: str = "authenticated"


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> AuthUser:
    settings = get_settings()
    token = credentials.credentials
    jwks = await _load_jwks()

    try:
        payload = _decode_with_keys(token, jwks, settings.SUPABASE_JWT_SECRET)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth_expired", "message": "Token has expired"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth_invalid", "message": "Invalid authentication credentials"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")  # type: ignore[assignment]
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth_invalid", "message": "Token missing subject"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthUser(
        id=user_id,
        email=payload.get("email"),  # type: ignore[arg-type]
        role=payload.get("role", "authenticated"),  # type: ignore[arg-type]
    )
