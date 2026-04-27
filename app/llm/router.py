"""Task-based LLM router: picks provider+model from config, logs every call."""
import time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import structlog
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import CostCapExceededError, LLMError, LLMProvider, LLMRequest, LLMResponse
from app.llm.openai_provider import OpenAIProvider
from app.llm.anthropic_provider import AnthropicProvider

log = structlog.get_logger()

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "llm_routing.yaml"


def _load_routing() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)["llm"]["routing"]


_ROUTING: dict = _load_routing()

_PROVIDERS: dict[str, LLMProvider] = {}


def _get_provider(name: str) -> LLMProvider:
    if name not in _PROVIDERS:
        from app.config import get_settings
        settings = get_settings()
        if name == "openai":
            _PROVIDERS[name] = OpenAIProvider(api_key=settings.OPENAI_API_KEY)
        elif name == "anthropic":
            _PROVIDERS[name] = AnthropicProvider()
        else:
            raise LLMError(f"Unknown provider: {name}")
    return _PROVIDERS[name]


async def _check_cost_cap(user_id: UUID, db: AsyncSession) -> None:
    from app.config import get_settings
    from app.db.models.ai_request_log import AiRequestLog
    from sqlalchemy import func, text

    settings = get_settings()
    result = await db.execute(
        select(func.coalesce(func.sum(AiRequestLog.cost_usd), 0)).where(
            AiRequestLog.user_id == user_id,
            AiRequestLog.status == "success",
            AiRequestLog.created_at > func.now() - text("interval '24 hours'"),
        )
    )
    daily_spend = float(result.scalar() or 0)
    if daily_spend >= settings.AI_COST_CAP_USD:
        raise CostCapExceededError(
            f"Daily AI spend cap of ${settings.AI_COST_CAP_USD:.2f} exceeded "
            f"(current: ${daily_spend:.4f})"
        )


async def execute(
    task: str,
    request: LLMRequest,
    user_id: UUID,
    db: AsyncSession,
    prompt_version: str | None = None,
) -> LLMResponse:
    if task not in _ROUTING:
        raise LLMError(f"Unknown task: {task}")

    route = _ROUTING[task]
    provider_name: str = route["provider"]
    model: str = route["model"]

    await _check_cost_cap(user_id, db)

    provider = _get_provider(provider_name)
    start = time.monotonic()
    status = "success"
    error_message: str | None = None
    response: LLMResponse | None = None

    try:
        response = await provider.complete(request, model)
    except CostCapExceededError:
        raise
    except Exception as exc:
        status = "error"
        error_message = str(exc)
        log.error("llm_call_failed", task=task, provider=provider_name, model=model, error=str(exc))
        raise LLMError(str(exc)) from exc
    finally:
        latency_ms = round((time.monotonic() - start) * 1000)

        from app.db.models.ai_request_log import AiRequestLog
        log_entry = AiRequestLog(
            user_id=user_id,
            task=task,
            provider=provider_name,
            model=model,
            prompt_version=prompt_version,
            input_tokens=response.usage.input_tokens if response else None,
            output_tokens=response.usage.output_tokens if response else None,
            cost_usd=Decimal(str(response.usage.cost_usd)) if response else None,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
        )
        db.add(log_entry)
        await db.commit()

        if response:
            log.info(
                "llm_call",
                task=task,
                provider=provider_name,
                model=model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd=round(response.usage.cost_usd, 6),
                latency_ms=latency_ms,
            )

    return response  # type: ignore[return-value]
