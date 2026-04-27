"""Competition search, caching, and saved-competitions service."""
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.competition import Competition
from app.db.models.saved_competition import SavedCompetition

_CACHE_TTL_DAYS = 7


def _is_fresh(comp: Competition) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=_CACHE_TTL_DAYS)
    return comp.refreshed_at >= cutoff


async def search_competitions(
    db: AsyncSession,
    division: str | None = None,
    tested: bool | None = None,
    start: date | None = None,
    end: date | None = None,
    federation: str | None = None,
    limit: int = 20,
) -> tuple[list[Competition], str]:
    q = select(Competition)
    if division:
        from sqlalchemy import cast, String
        from sqlalchemy.dialects.postgresql import JSONB
        q = q.where(Competition.divisions.contains([division]))
    if tested is not None:
        q = q.where(Competition.tested == tested)
    if start:
        q = q.where(Competition.date >= start)
    if end:
        q = q.where(Competition.date <= end)
    if federation:
        q = q.where(Competition.federation == federation)
    q = q.order_by(Competition.date.asc()).limit(limit)

    result = await db.execute(q)
    comps = list(result.scalars().all())

    all_fresh = all(_is_fresh(c) for c in comps) if comps else False
    cache_status = "fresh" if all_fresh else "stale"
    return comps, cache_status


async def get_competition(db: AsyncSession, comp_id: UUID) -> Competition | None:
    result = await db.execute(select(Competition).where(Competition.id == comp_id))
    return result.scalar_one_or_none()


async def upsert_competition(db: AsyncSession, data: dict[str, Any]) -> Competition:
    existing = await db.execute(
        select(Competition).where(
            Competition.name == data["name"],
            Competition.date == data["date"],
            Competition.federation == data["federation"],
        )
    )
    comp = existing.scalar_one_or_none()
    if comp:
        for k, v in data.items():
            setattr(comp, k, v)
        comp.refreshed_at = datetime.now(timezone.utc)
    else:
        comp = Competition(**data)
        db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


async def save_competition(
    db: AsyncSession, user_id: UUID, comp_id: UUID
) -> SavedCompetition:
    comp = await get_competition(db, comp_id)
    if not comp:
        raise ValueError("Competition not found")

    existing = await db.execute(
        select(SavedCompetition).where(
            SavedCompetition.user_id == user_id,
            SavedCompetition.competition_id == comp_id,
        )
    )
    saved = existing.scalar_one_or_none()
    if saved:
        return saved

    snapshot = {
        "name": comp.name,
        "date": comp.date.isoformat() if comp.date else None,
        "federation": comp.federation,
        "tested": comp.tested,
        "city": comp.city,
        "state": comp.state,
        "country": comp.country,
        "divisions": comp.divisions,
        "registration_url": comp.registration_url,
    }
    saved = SavedCompetition(
        user_id=user_id,
        competition_id=comp_id,
        snapshot=snapshot,
    )
    db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return saved


async def list_saved_competitions(
    db: AsyncSession, user_id: UUID
) -> list[SavedCompetition]:
    result = await db.execute(
        select(SavedCompetition)
        .where(SavedCompetition.user_id == user_id)
        .order_by(SavedCompetition.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_saved_competition(
    db: AsyncSession, user_id: UUID, comp_id: UUID
) -> bool:
    result = await db.execute(
        select(SavedCompetition).where(
            SavedCompetition.user_id == user_id,
            SavedCompetition.competition_id == comp_id,
        )
    )
    saved = result.scalar_one_or_none()
    if not saved:
        return False
    await db.delete(saved)
    await db.commit()
    return True
