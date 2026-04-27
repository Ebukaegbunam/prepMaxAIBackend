"""Developer test endpoints — gated off in production by TestGateMiddleware."""
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from jose import jwt as jose_jwt
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.llm.base import LLMRequest, Message

router = APIRouter(prefix="/__test__", tags=["test"])

_FAKE_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_FAKE_EMAIL = "dev@prepai.local"


@router.get("/token")
async def dev_token(db: AsyncSession = Depends(get_db)) -> dict:
    """Return a pre-signed JWT for the fixed dev user, seeding auth.users if needed."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    # Seed the dev user into auth.users so FK constraints are satisfied.
    await db.execute(
        text("""
            INSERT INTO auth.users (
                id, instance_id, aud, role, email,
                encrypted_password, email_confirmed_at,
                raw_app_meta_data, raw_user_meta_data,
                created_at, updated_at, is_super_admin
            ) VALUES (
                :uid,
                '00000000-0000-0000-0000-000000000000',
                'authenticated', 'authenticated', :email,
                '', NOW(),
                '{"provider":"dev","providers":["dev"]}'::jsonb,
                '{"name":"Dev User"}'::jsonb,
                NOW(), NOW(), false
            )
            ON CONFLICT (id) DO NOTHING
        """),
        {"uid": str(_FAKE_USER_ID), "email": _FAKE_EMAIL},
    )
    await db.commit()

    token = jose_jwt.encode(
        {
            "sub": str(_FAKE_USER_ID),
            "email": _FAKE_EMAIL,
            "aud": "authenticated",
            "role": "authenticated",
            "exp": int(expires_at.timestamp()),
            "iat": int(now.timestamp()),
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    return {
        "token": token,
        "user_id": str(_FAKE_USER_ID),
        "email": _FAKE_EMAIL,
        "expires_at": expires_at.isoformat(),
    }


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


class SeedSessionRequest(BaseModel):
    prep_id: UUID
    user_id: UUID
    canonical_exercise_id: UUID


class SeedSessionResponse(BaseModel):
    session_id: UUID
    set_ids: list[UUID]


@router.post("/seed-session", response_model=SeedSessionResponse)
async def seed_session(
    body: SeedSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> SeedSessionResponse:
    from app.db.models.set_log import SetLog
    from app.db.models.workout_session import WorkoutSession

    now = datetime.now(timezone.utc)
    session = WorkoutSession(
        user_id=body.user_id,
        prep_id=body.prep_id,
        started_at=now,
        title="Test Session",
    )
    db.add(session)
    await db.flush()

    sets_data = [
        {"weight_kg": 80, "reps": 10, "set_number": 1},
        {"weight_kg": 85, "reps": 8, "set_number": 2},
        {"weight_kg": 90, "reps": 6, "set_number": 3},
    ]
    set_logs = []
    for s in sets_data:
        log = SetLog(
            user_id=body.user_id,
            workout_session_id=session.id,
            canonical_exercise_id=body.canonical_exercise_id,
            exercise_name_raw="Test Exercise",
            set_number=s["set_number"],
            weight_kg=s["weight_kg"],
            reps=s["reps"],
            performed_at=now,
        )
        db.add(log)
        set_logs.append(log)

    await db.commit()
    await db.refresh(session)
    for log in set_logs:
        await db.refresh(log)

    return SeedSessionResponse(session_id=session.id, set_ids=[log.id for log in set_logs])


class CalorieEngineTestRequest(BaseModel):
    weight_kg: float
    height_cm: float
    age: int
    sex: str
    training_days_per_week: int
    prep_length_weeks: int = 16
    maintenance_weeks: int = 4
    week_number: int = 1


@router.post("/calorie-engine")
async def test_calorie_engine(body: CalorieEngineTestRequest) -> dict:
    from app.lib.calorie_engine import bmr, tdee, targets_for_week
    bmr_val = bmr(body.weight_kg, body.height_cm, body.age, body.sex)
    tdee_val = tdee(bmr_val, body.training_days_per_week)
    targets = targets_for_week(
        prep_length_weeks=body.prep_length_weeks,
        week_number=body.week_number,
        maintenance_weeks=body.maintenance_weeks,
        tdee_kcal=tdee_val,
        weight_kg=body.weight_kg,
    )
    return {"bmr": round(bmr_val, 2), "tdee": round(tdee_val, 2), "targets": targets}


class EstimateMacrosTestRequest(BaseModel):
    description: str


@router.post("/estimate-macros")
async def test_estimate_macros(
    body: EstimateMacrosTestRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.llm import router as llm_router
    from app.llm.prompts.estimate_macros import RESPONSE_SCHEMA, VERSION, build_messages
    raw_messages = build_messages(body.description)
    response = await llm_router.execute(
        task="estimate_macros",
        request=LLMRequest(messages=[Message(**m) for m in raw_messages], response_schema=RESPONSE_SCHEMA, temperature=0.2),
        user_id=_FAKE_USER_ID,
        db=db,
        prompt_version=VERSION,
    )
    return response.structured or {}
