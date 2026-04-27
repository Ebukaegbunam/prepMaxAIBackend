"""HTTP request rate limiter: 1000 req / 24h per authenticated user."""
from datetime import datetime, timezone, timedelta
from uuid import UUID

import structlog
from jose import JWTError, jwt
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = structlog.get_logger()

_EXEMPT_PREFIXES = ("/health", "/ready", "/auth/", "/__test__", "/__docs__", "/openapi")


def _is_exempt(path: str) -> bool:
    return any(path.startswith(p) for p in _EXEMPT_PREFIXES)


def _extract_user_id(token: str, jwt_secret: str) -> UUID | None:
    try:
        payload = jwt.decode(
            token, jwt_secret, algorithms=["HS256"],
            audience="authenticated", options={"verify_exp": False},
        )
        sub = payload.get("sub")
        return UUID(sub) if sub else None
    except (JWTError, ValueError):
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        if _is_exempt(request.url.path):
            return await call_next(request)  # type: ignore[arg-type]

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)  # type: ignore[arg-type]

        from app.config import get_settings
        settings = get_settings()
        user_id = _extract_user_id(auth_header[7:], settings.SUPABASE_JWT_SECRET)
        if not user_id:
            return await call_next(request)  # type: ignore[arg-type]

        from app.db.session import AsyncSessionLocal
        from app.db.models.rate_limit_counter import RateLimitCounter

        async with AsyncSessionLocal() as db:
            # Check total in last 24h
            result = await db.execute(
                select(func.coalesce(func.sum(RateLimitCounter.count), 0)).where(
                    RateLimitCounter.user_id == user_id,
                    RateLimitCounter.hour_bucket > func.now() - text("interval '24 hours'"),
                )
            )
            total: int = int(result.scalar() or 0)

            if total >= settings.RATE_LIMIT_MAX_REQUESTS:
                log.warning("rate_limit_exceeded", user_id=str(user_id), total=total)
                return JSONResponse(
                    {
                        "error": {
                            "code": "rate_limited",
                            "message": "Rate limit exceeded. Try again later.",
                            "retry_after": 3600,
                        }
                    },
                    status_code=429,
                    headers={"Retry-After": "3600"},
                )

            # Increment current-hour bucket
            current_hour = datetime.now(timezone.utc).replace(
                minute=0, second=0, microsecond=0
            )
            stmt = (
                pg_insert(RateLimitCounter)
                .values(user_id=user_id, hour_bucket=current_hour, count=1)
                .on_conflict_do_update(
                    index_elements=["user_id", "hour_bucket"],
                    set_={"count": RateLimitCounter.count + 1},
                )
            )
            await db.execute(stmt)
            await db.commit()

        return await call_next(request)  # type: ignore[arg-type]
