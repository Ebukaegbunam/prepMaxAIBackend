"""Prep CRUD service."""
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.prep import Prep


async def list_preps(user_id: UUID, db: AsyncSession) -> list[Prep]:
    result = await db.execute(
        select(Prep).where(Prep.user_id == user_id).order_by(Prep.created_at.desc())
    )
    return list(result.scalars().all())


async def get_prep(prep_id: UUID, user_id: UUID, db: AsyncSession) -> Prep | None:
    result = await db.execute(
        select(Prep).where(Prep.id == prep_id, Prep.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_prep(user_id: UUID, data: dict, db: AsyncSession) -> Prep:
    start_date: date = data["start_date"]
    weeks: int = data.get("prep_length_weeks", 16)
    target_date = start_date + timedelta(weeks=weeks)

    prep = Prep(
        user_id=user_id,
        target_date=target_date,
        **data,
    )
    db.add(prep)
    await db.commit()
    await db.refresh(prep)
    return prep


async def patch_prep(prep: Prep, updates: dict, db: AsyncSession) -> Prep:
    for key, value in updates.items():
        setattr(prep, key, value)
    await db.commit()
    await db.refresh(prep)
    return prep


async def complete_prep(prep: Prep, notes: str | None, db: AsyncSession) -> Prep:
    prep.status = "completed"
    if notes:
        prep.completion_notes = notes
    await db.commit()
    await db.refresh(prep)
    return prep
