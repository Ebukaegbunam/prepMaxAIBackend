import logging
from pathlib import Path

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import get_settings
from app.llm.base import CostCapExceededError, LLMError
from app.middleware.logging_mw import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.test_gate import TestGateMiddleware
from app.routes import admin, ai_routes, auth, competitions, health, meals, preps, profile, progress, sessions, test_endpoints, workouts


def _configure_structlog(log_level: str, is_production: bool) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_structlog(settings.LOG_LEVEL, settings.is_production)

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            environment=settings.APP_ENV,
            release=settings.APP_VERSION,
            traces_sample_rate=0.1,
        )

    app = FastAPI(
        title="PrepAI Backend",
        version=settings.APP_VERSION,
        docs_url="/__docs__" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # Middleware — first add_middleware = outermost = processes requests first
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TestGateMiddleware)

    @app.exception_handler(FastAPIHTTPException)
    async def _http_exception_handler(request: Request, exc: FastAPIHTTPException) -> JSONResponse:
        # Unwrap our {error: {code, message}} detail into the root so the client
        # always sees {"error": {...}} instead of {"detail": {"error": {...}}}.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            content = exc.detail
        else:
            content = {"error": {"code": "http_error", "message": str(exc.detail)}}
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=dict(exc.headers) if exc.headers else {},
        )

    @app.exception_handler(CostCapExceededError)
    async def _cost_cap_handler(request: Request, exc: CostCapExceededError) -> JSONResponse:
        log = structlog.get_logger()
        log.warning("cost_cap_exceeded", error=str(exc))
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "cost_cap_exceeded", "message": str(exc)}},
        )

    @app.exception_handler(LLMError)
    async def _llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
        log = structlog.get_logger()
        log.error("ai_provider_error", error=str(exc))
        return JSONResponse(
            status_code=502,
            content={"error": {"code": "ai_provider_error", "message": "AI provider returned an error"}},
        )

    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log = structlog.get_logger()
        log.error("unhandled_exception", error=str(exc), exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "An unexpected error occurred"}},
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(preps.router)
    app.include_router(workouts.router)
    app.include_router(sessions.router)
    app.include_router(meals.router)
    app.include_router(progress.router)
    app.include_router(competitions.router)
    app.include_router(ai_routes.router)
    app.include_router(admin.router)
    app.include_router(test_endpoints.router)

    # Test UI — gated by TestGateMiddleware (returns 404 in production)
    _static_dir = Path(__file__).parent / "static"
    if _static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    @app.get("/__test__/ui", include_in_schema=False)
    async def test_ui() -> FileResponse:
        return FileResponse(str(_static_dir / "test_ui" / "index.html"))

    return app


app = create_app()
