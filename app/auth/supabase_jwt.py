from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

_bearer = HTTPBearer()


class AuthUser(BaseModel):
    id: str
    email: str | None = None
    role: str = "authenticated"


def _decode_token(token: str, jwt_secret: str) -> dict[str, object]:
    return jwt.decode(
        token,
        jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
        options={"verify_exp": True},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> AuthUser:
    settings = get_settings()
    token = credentials.credentials

    try:
        payload = _decode_token(token, settings.SUPABASE_JWT_SECRET)
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
