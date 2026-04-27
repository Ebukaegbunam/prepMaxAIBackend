import hashlib
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger()


def _hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        start = time.monotonic()

        response: Response = await call_next(request)  # type: ignore[arg-type]

        latency_ms = round((time.monotonic() - start) * 1000, 2)

        # Extract user_id from request state if auth middleware set it
        user_id_hash: str | None = None
        if hasattr(request.state, "user_id"):
            user_id_hash = _hash_user_id(request.state.user_id)

        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
            user_id_hash=user_id_hash,
        )

        return response
