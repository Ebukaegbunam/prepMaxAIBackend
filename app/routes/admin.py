"""Admin endpoints — protected by X-Admin-Token header."""
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db

router = APIRouter(prefix="/__admin__", tags=["admin"])
log = structlog.get_logger()

_startup_time = time.monotonic()


def _require_admin_token(x_admin_token: str = Header(alias="X-Admin-Token", default="")) -> None:
    settings = get_settings()
    if not settings.ADMIN_TOKEN or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Invalid or missing admin token"}},
        )


AdminGuard = Annotated[None, Depends(_require_admin_token)]


@router.get("/cost-rollup")
async def cost_rollup(
    _: AdminGuard,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=90),
) -> dict:
    from app.db.models.ai_request_log import AiRequestLog
    from sqlalchemy import cast, Date

    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            cast(AiRequestLog.created_at, Date).label("day"),
            AiRequestLog.task,
            func.count().label("calls"),
            func.coalesce(func.sum(AiRequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(AiRequestLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(AiRequestLog.cost_usd), 0).label("cost_usd"),
        )
        .where(AiRequestLog.created_at >= since)
        .group_by(cast(AiRequestLog.created_at, Date), AiRequestLog.task)
        .order_by(cast(AiRequestLog.created_at, Date).desc(), AiRequestLog.task)
    )
    rows = result.all()

    total_result = await db.execute(
        select(
            func.coalesce(func.sum(AiRequestLog.cost_usd), 0).label("total_cost"),
            func.count().label("total_calls"),
        ).where(AiRequestLog.created_at >= since)
    )
    totals = total_result.one()

    return {
        "days": days,
        "since": since.isoformat(),
        "total_cost_usd": float(totals.total_cost),
        "total_calls": totals.total_calls,
        "breakdown": [
            {
                "day": str(r.day),
                "task": r.task,
                "calls": r.calls,
                "input_tokens": int(r.input_tokens),
                "output_tokens": int(r.output_tokens),
                "cost_usd": float(r.cost_usd),
            }
            for r in rows
        ],
    }


@router.get("/rate-limit/{user_id}")
async def rate_limit_status(
    user_id: UUID,
    _: AdminGuard,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.db.models.rate_limit_counter import RateLimitCounter

    settings = get_settings()
    result = await db.execute(
        select(
            func.coalesce(func.sum(RateLimitCounter.count), 0).label("count"),
        ).where(
            RateLimitCounter.user_id == user_id,
            RateLimitCounter.hour_bucket > func.now() - text("interval '24 hours'"),
        )
    )
    current_count = int(result.scalar() or 0)

    return {
        "user_id": str(user_id),
        "window_hours": settings.RATE_LIMIT_WINDOW_HOURS,
        "limit": settings.RATE_LIMIT_MAX_REQUESTS,
        "current_count": current_count,
        "remaining": max(0, settings.RATE_LIMIT_MAX_REQUESTS - current_count),
        "is_limited": current_count >= settings.RATE_LIMIT_MAX_REQUESTS,
    }


@router.get("/health/deep")
async def health_deep(
    _: AdminGuard,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.db.models.ai_request_log import AiRequestLog

    settings = get_settings()
    checks: dict[str, object] = {}

    # Database round-trip
    try:
        start = time.monotonic()
        await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.monotonic() - start) * 1000, 1)
        checks["database"] = {"status": "ok", "latency_ms": db_latency_ms}
    except Exception as exc:
        log.error("deep_health_db_failed", error=str(exc))
        checks["database"] = {"status": "error", "error": str(exc)}

    # LLM provider key presence
    checks["openai_key"] = {"status": "ok" if settings.OPENAI_API_KEY else "missing"}
    checks["anthropic_key"] = {"status": "ok" if settings.ANTHROPIC_API_KEY else "missing"}
    checks["sentry"] = {"status": "ok" if settings.SENTRY_DSN else "not_configured"}

    # AI spend last 24h
    try:
        spend_result = await db.execute(
            select(func.coalesce(func.sum(AiRequestLog.cost_usd), 0)).where(
                AiRequestLog.created_at > func.now() - text("interval '24 hours'"),
                AiRequestLog.status == "success",
            )
        )
        daily_spend = float(spend_result.scalar() or 0)
        checks["ai_cost_24h"] = {
            "spend_usd": round(daily_spend, 4),
            "cap_usd": settings.AI_COST_CAP_USD,
            "pct_used": round(daily_spend / settings.AI_COST_CAP_USD * 100, 1) if settings.AI_COST_CAP_USD else 0,
        }
    except Exception as exc:
        checks["ai_cost_24h"] = {"status": "error", "error": str(exc)}

    all_ok = all(
        (v.get("status") if isinstance(v, dict) else True) == "ok"
        for k, v in checks.items()
        if k not in ("sentry", "anthropic_key")
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "uptime_seconds": round(time.monotonic() - _startup_time, 1),
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "checks": checks,
    }
