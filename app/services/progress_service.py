from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_report import AiReport
from app.db.models.check_in import CheckIn
from app.db.models.measurement_log import MeasurementLog
from app.db.models.photo import Photo
from app.db.models.weight_log import WeightLog
from app.schemas.progress import (
    CheckInCreate,
    MeasurementLogCreate,
    PhotoRegisterRequest,
    WeightLogCreate,
    WeightTrend,
)


def compute_trend(logs: list[WeightLog]) -> WeightTrend:
    """Compute 7-day moving average trend from weight logs."""
    if not logs:
        return WeightTrend(current_avg_7d=None, previous_avg_7d=None, delta_kg=None, trajectory="insufficient_data")

    now = datetime.now(timezone.utc)
    cutoff_current = now - timedelta(days=7)
    cutoff_previous = now - timedelta(days=14)

    current_week = [float(log.weight_kg) for log in logs if log.logged_at >= cutoff_current]
    previous_week = [float(log.weight_kg) for log in logs if cutoff_previous <= log.logged_at < cutoff_current]

    current_avg = sum(current_week) / len(current_week) if current_week else None
    previous_avg = sum(previous_week) / len(previous_week) if previous_week else None

    delta = None
    trajectory = "insufficient_data"
    if current_avg is not None and previous_avg is not None:
        delta = round(current_avg - previous_avg, 2)
        if delta <= -0.1:
            trajectory = "on_track"
        elif delta > 0.3:
            trajectory = "gaining"
        else:
            trajectory = "maintaining"

    return WeightTrend(
        current_avg_7d=round(current_avg, 2) if current_avg else None,
        previous_avg_7d=round(previous_avg, 2) if previous_avg else None,
        delta_kg=delta,
        trajectory=trajectory,
    )


async def log_weight(
    db: AsyncSession, user_id: UUID, prep_id: UUID, data: WeightLogCreate
) -> WeightLog:
    log = WeightLog(
        user_id=user_id,
        prep_id=prep_id,
        logged_at=data.logged_at or datetime.now(timezone.utc),
        weight_kg=data.weight_kg,
        source=data.source,
        notes=data.notes,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_weights(
    db: AsyncSession,
    user_id: UUID,
    prep_id: UUID,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> list[WeightLog]:
    q = select(WeightLog).where(
        WeightLog.user_id == user_id,
        WeightLog.prep_id == prep_id,
    )
    if from_dt:
        q = q.where(WeightLog.logged_at >= from_dt)
    if to_dt:
        q = q.where(WeightLog.logged_at <= to_dt)
    result = await db.execute(q.order_by(WeightLog.logged_at.desc()))
    return list(result.scalars().all())


async def log_measurement(
    db: AsyncSession, user_id: UUID, prep_id: UUID, data: MeasurementLogCreate
) -> MeasurementLog:
    log = MeasurementLog(
        user_id=user_id,
        prep_id=prep_id,
        logged_at=data.logged_at or datetime.now(timezone.utc),
        **{k: v for k, v in data.model_dump(exclude={"logged_at"}).items() if v is not None},
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_measurements(
    db: AsyncSession, user_id: UUID, prep_id: UUID
) -> list[MeasurementLog]:
    result = await db.execute(
        select(MeasurementLog)
        .where(MeasurementLog.user_id == user_id, MeasurementLog.prep_id == prep_id)
        .order_by(MeasurementLog.logged_at.desc())
    )
    return list(result.scalars().all())


async def register_photo(
    db: AsyncSession, user_id: UUID, prep_id: UUID, data: PhotoRegisterRequest
) -> Photo:
    photo = Photo(
        user_id=user_id,
        prep_id=prep_id,
        storage_key=data.storage_key,
        taken_at=data.taken_at,
        week_number=data.week_number,
        angle=data.angle,
        body_part=data.body_part,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


async def get_photo(db: AsyncSession, photo_id: UUID, user_id: UUID) -> Photo | None:
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_photos(
    db: AsyncSession,
    user_id: UUID,
    prep_id: UUID,
    body_part: str | None = None,
    week: int | None = None,
) -> list[Photo]:
    q = select(Photo).where(Photo.user_id == user_id, Photo.prep_id == prep_id)
    if body_part:
        q = q.where(Photo.body_part == body_part)
    if week is not None:
        q = q.where(Photo.week_number == week)
    result = await db.execute(q.order_by(Photo.taken_at.desc()))
    return list(result.scalars().all())


async def delete_photo(db: AsyncSession, photo: Photo) -> None:
    await db.delete(photo)
    await db.commit()


async def create_check_in(
    db: AsyncSession, user_id: UUID, prep_id: UUID, data: CheckInCreate
) -> CheckIn:
    check_in = CheckIn(
        user_id=user_id,
        prep_id=prep_id,
        week_number=data.week_number,
        completed_at=data.completed_at,
        weight_kg=data.weight_kg,
        mood=data.mood,
        energy=data.energy,
        sleep=data.sleep,
        training_quality=data.training_quality,
        notes=data.notes,
        measurement_log_id=data.measurement_log_id,
    )
    db.add(check_in)
    await db.commit()
    await db.refresh(check_in)
    return check_in


async def list_check_ins(
    db: AsyncSession, user_id: UUID, prep_id: UUID
) -> list[CheckIn]:
    result = await db.execute(
        select(CheckIn)
        .where(CheckIn.user_id == user_id, CheckIn.prep_id == prep_id)
        .order_by(CheckIn.week_number.desc())
    )
    return list(result.scalars().all())


async def get_check_in(db: AsyncSession, check_in_id: UUID, user_id: UUID) -> CheckIn | None:
    result = await db.execute(
        select(CheckIn).where(CheckIn.id == check_in_id, CheckIn.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_ai_report(
    db: AsyncSession, user_id: UUID, prep_id: UUID, week_number: int
) -> AiReport | None:
    result = await db.execute(
        select(AiReport).where(
            AiReport.user_id == user_id,
            AiReport.prep_id == prep_id,
            AiReport.week_number == week_number,
        )
    )
    return result.scalar_one_or_none()


async def save_ai_report(
    db: AsyncSession,
    user_id: UUID,
    prep_id: UUID,
    week_number: int,
    content: dict,
    ai_request_id: UUID | None = None,
) -> AiReport:
    existing = await get_ai_report(db, user_id, prep_id, week_number)
    if existing:
        existing.content = content
        existing.ai_request_id = ai_request_id
    else:
        existing = AiReport(
            user_id=user_id,
            prep_id=prep_id,
            week_number=week_number,
            content=content,
            ai_request_id=ai_request_id,
        )
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return existing


async def list_reports(
    db: AsyncSession, user_id: UUID, prep_id: UUID
) -> list[AiReport]:
    result = await db.execute(
        select(AiReport)
        .where(AiReport.user_id == user_id, AiReport.prep_id == prep_id)
        .order_by(AiReport.week_number.desc())
    )
    return list(result.scalars().all())


async def get_report_by_id(
    db: AsyncSession, report_id: UUID, user_id: UUID
) -> AiReport | None:
    result = await db.execute(
        select(AiReport).where(AiReport.id == report_id, AiReport.user_id == user_id)
    )
    return result.scalar_one_or_none()
