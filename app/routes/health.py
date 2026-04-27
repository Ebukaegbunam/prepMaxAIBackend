import time

import httpx
import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_engine

router = APIRouter(tags=["system"])
log = structlog.get_logger()

_startup_time = time.monotonic()


@router.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "uptime_seconds": round(time.monotonic() - _startup_time, 1),
    }


@router.get("/ready")
async def ready() -> JSONResponse:
    checks: dict[str, str] = {}
    all_ok = True

    # Database check
    try:
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine = get_engine()
        async with engine.connect() as conn:  # type: ignore[union-attr]
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        log.warning("readiness_check_failed", check="database", error=str(exc))
        checks["database"] = "error"
        all_ok = False

    # LLM provider check (verify key is configured — no live call)
    settings = get_settings()
    if settings.OPENAI_API_KEY:
        checks["llm_provider"] = "ok"
    else:
        checks["llm_provider"] = "error"
        all_ok = False

    # Storage check (verify Supabase is reachable)
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{settings.SUPABASE_URL}/rest/v1/",
                    headers={"apikey": settings.SUPABASE_ANON_KEY},
                )
                checks["storage"] = "ok" if resp.status_code < 500 else "error"
                if resp.status_code >= 500:
                    all_ok = False
        except Exception as exc:
            log.warning("readiness_check_failed", check="storage", error=str(exc))
            checks["storage"] = "error"
            all_ok = False
    else:
        checks["storage"] = "error"
        all_ok = False

    status_code = 200 if all_ok else 503
    return JSONResponse(
        {"status": "ready" if all_ok else "not_ready", "checks": checks},
        status_code=status_code,
    )
