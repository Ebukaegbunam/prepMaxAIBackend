"""Profile CRUD and narrative generation orchestration."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.profile import Profile
from app.llm import router as llm_router
from app.llm.base import LLMRequest, Message
from app.llm import prompts


async def get_profile(user_id: UUID, db: AsyncSession) -> Profile | None:
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    return result.scalar_one_or_none()


async def _generate_narrative(
    profile_data: dict,
    free_text: str | None,
    user_id: UUID,
    db: AsyncSession,
) -> str:
    from app.llm.prompts.update_narrative import build_messages, RESPONSE_SCHEMA, VERSION

    raw_messages = build_messages(profile_data, free_text)
    request = LLMRequest(
        messages=[Message(**m) for m in raw_messages],
        response_schema=RESPONSE_SCHEMA,
        temperature=0.6,
        max_tokens=400,
    )
    response = await llm_router.execute(
        task="update_narrative",
        request=request,
        user_id=user_id,
        db=db,
        prompt_version=VERSION,
    )

    if response.structured and "narrative" in response.structured:
        return response.structured["narrative"]
    # Fallback: use raw text if structured parsing failed
    return response.text.strip()


def _profile_to_dict(data: dict) -> dict:
    """Strip internal fields before sending to LLM."""
    exclude = {"id", "user_id", "narrative", "narrative_updated_at", "created_at", "updated_at",
               "free_text_about_me", "free_text_update"}
    return {k: v for k, v in data.items() if k not in exclude and v is not None}


async def initialize_profile(
    user_id: UUID,
    data: dict,
    db: AsyncSession,
) -> Profile:
    existing = await get_profile(user_id, db)
    if existing:
        return existing

    free_text = data.pop("free_text_about_me", None)

    profile = Profile(user_id=user_id, **data)
    db.add(profile)
    await db.flush()  # assign ID without committing

    narrative = await _generate_narrative(
        _profile_to_dict(data),
        free_text,
        user_id,
        db,
    )
    profile.narrative = narrative
    profile.narrative_updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return profile


async def patch_profile(
    user_id: UUID,
    updates: dict,
    db: AsyncSession,
) -> Profile:
    profile = await get_profile(user_id, db)
    if profile is None:
        raise ValueError("Profile not found")

    free_text = updates.pop("free_text_update", None)

    for key, value in updates.items():
        setattr(profile, key, value)

    if free_text:
        narrative = await _generate_narrative(
            _profile_to_dict(
                {c.key: getattr(profile, c.key) for c in Profile.__table__.columns}
            ),
            free_text,
            user_id,
            db,
        )
        profile.narrative = narrative
        profile.narrative_updated_at = datetime.now(timezone.utc)

    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return profile
