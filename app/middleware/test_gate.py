import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings

log = structlog.get_logger()

_BLOCKED_PREFIXES = ("/__test__/", "/__test__")


class TestGateMiddleware(BaseHTTPMiddleware):
    """Block test and admin-test endpoints in production."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        settings = get_settings()
        path = request.url.path

        if settings.is_production and any(path.startswith(p) for p in _BLOCKED_PREFIXES):
            return JSONResponse(
                {"error": {"code": "not_found", "message": "Not found"}},
                status_code=404,
            )

        return await call_next(request)  # type: ignore[return-value,arg-type]
