"""Developer test endpoints — gated off in production by TestGateMiddleware."""
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.llm.base import LLMRequest, Message

router = APIRouter(prefix="/__test__", tags=["test"])

_FAKE_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class NarrativeTestRequest(BaseModel):
    name: str
    age: int | None = None
    sex: str | None = None
    job_type: str | None = None
    stress_level: str | None = None
    preferred_training_time: str | None = None
    training_days_per_week: int | None = None
    dietary_restrictions: list[str] = []
    loved_foods: list[str] = []
    hated_foods: list[str] = []
    cooking_skill: str | None = None
    free_text_about_me: str | None = None


class NarrativeTestResponse(BaseModel):
    narrative: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@router.post("/profile/regenerate-narrative", response_model=NarrativeTestResponse)
async def test_regenerate_narrative(
    body: NarrativeTestRequest,
    db: AsyncSession = Depends(get_db),
) -> NarrativeTestResponse:
    from app.llm import router as llm_router
    from app.llm.prompts.update_narrative import RESPONSE_SCHEMA, VERSION, build_messages

    structured = body.model_dump(exclude={"free_text_about_me"}, exclude_none=True)
    raw_messages = build_messages(structured, body.free_text_about_me)

    request = LLMRequest(
        messages=[Message(**m) for m in raw_messages],
        response_schema=RESPONSE_SCHEMA,
        temperature=0.6,
        max_tokens=400,
    )
    response = await llm_router.execute(
        task="update_narrative",
        request=request,
        user_id=_FAKE_USER_ID,
        db=db,
        prompt_version=VERSION,
    )

    narrative = (
        response.structured["narrative"]
        if response.structured and "narrative" in response.structured
        else response.text.strip()
    )

    return NarrativeTestResponse(
        narrative=narrative,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost_usd=response.usage.cost_usd,
    )


@router.get("/rate-limit/status")
async def rate_limit_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return {"message": "Rate limit status — pass user JWT to see real count"}


@router.post("/rate-limit/reset")
async def rate_limit_reset(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    return {"message": "Reset endpoint — authenticate to reset your own counter"}
