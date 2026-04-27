from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cardio_log import CardioLog
from app.db.models.canonical_exercise import CanonicalExercise
from app.db.models.set_log import SetLog
from app.db.models.workout_exercise import Exercise
from app.db.models.workout_session import WorkoutSession
from app.lib.one_rm import SetRecord, best_set, epley, total_volume_kg
from app.schemas.session import (
    CardioLogCreate,
    ExerciseHistoryResponse,
    SessionCreate,
    SessionHistoryEntry,
    SessionPatch,
    SetCreate,
    SetPatch,
)


async def list_sessions(
    db: AsyncSession,
    user_id: UUID,
    prep_id: UUID,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> list[WorkoutSession]:
    q = select(WorkoutSession).where(
        WorkoutSession.user_id == user_id,
        WorkoutSession.prep_id == prep_id,
    )
    if from_dt:
        q = q.where(WorkoutSession.started_at >= from_dt)
    if to_dt:
        q = q.where(WorkoutSession.started_at <= to_dt)
    q = q.order_by(WorkoutSession.started_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_session(
    db: AsyncSession,
    user_id: UUID,
    prep_id: UUID,
    data: SessionCreate,
) -> WorkoutSession:
    session = WorkoutSession(
        user_id=user_id,
        prep_id=prep_id,
        workout_day_id=data.workout_day_id,
        started_at=data.started_at,
        title=data.title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: UUID, user_id: UUID) -> WorkoutSession | None:
    result = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.id == session_id,
            WorkoutSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def patch_session(
    db: AsyncSession,
    session: WorkoutSession,
    data: SessionPatch,
) -> WorkoutSession:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(session, field, value)
    await db.commit()
    await db.refresh(session)
    return session


async def create_set(
    db: AsyncSession,
    user_id: UUID,
    workout_session: WorkoutSession,
    data: SetCreate,
) -> SetLog:
    canonical_exercise_id: UUID | None = None
    exercise_name_raw = data.exercise_name_raw

    if data.exercise_id:
        ex_result = await db.execute(
            select(Exercise).where(Exercise.id == data.exercise_id)
        )
        ex = ex_result.scalar_one_or_none()
        if ex:
            canonical_exercise_id = ex.canonical_exercise_id
            exercise_name_raw = ex.raw_name

    performed_at = data.performed_at or datetime.now()

    log = SetLog(
        user_id=user_id,
        workout_session_id=workout_session.id,
        exercise_id=data.exercise_id,
        canonical_exercise_id=canonical_exercise_id,
        exercise_name_raw=exercise_name_raw,
        set_number=data.set_number,
        weight_kg=data.weight_kg,
        reps=data.reps,
        rpe=data.rpe,
        performed_at=performed_at,
        notes=data.notes,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_set(db: AsyncSession, set_id: UUID, user_id: UUID) -> SetLog | None:
    result = await db.execute(
        select(SetLog).where(SetLog.id == set_id, SetLog.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def patch_set(db: AsyncSession, log: SetLog, data: SetPatch) -> SetLog:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(log, field, value)
    await db.commit()
    await db.refresh(log)
    return log


async def delete_set(db: AsyncSession, log: SetLog) -> None:
    await db.delete(log)
    await db.commit()


async def get_exercise_history(
    db: AsyncSession,
    user_id: UUID,
    canonical_id: UUID,
    prep_id: UUID | None = None,
    limit: int = 20,
) -> ExerciseHistoryResponse:
    ce_result = await db.execute(
        select(CanonicalExercise).where(CanonicalExercise.id == canonical_id)
    )
    ce = ce_result.scalar_one_or_none()
    canonical_name = ce.name if ce else str(canonical_id)

    q = (
        select(SetLog)
        .where(
            SetLog.user_id == user_id,
            SetLog.canonical_exercise_id == canonical_id,
        )
        .order_by(SetLog.performed_at.desc())
    )
    if prep_id:
        session_subq = (
            select(WorkoutSession.id)
            .where(WorkoutSession.prep_id == prep_id, WorkoutSession.user_id == user_id)
            .scalar_subquery()
        )
        q = q.where(SetLog.workout_session_id.in_(session_subq))

    result = await db.execute(q)
    all_sets = list(result.scalars().all())

    sessions_map: dict[UUID, list[SetLog]] = {}
    session_times: dict[UUID, datetime] = {}
    for s in all_sets:
        sessions_map.setdefault(s.workout_session_id, []).append(s)
        if s.workout_session_id not in session_times:
            session_times[s.workout_session_id] = s.performed_at

    sorted_session_ids = sorted(
        sessions_map.keys(),
        key=lambda sid: session_times[sid],
        reverse=True,
    )[:limit]

    history_entries: list[SessionHistoryEntry] = []
    all_time_records: list[SetRecord] = []

    for sid in sorted_session_ids:
        sets_in_session = sessions_map[sid]
        records: list[SetRecord] = [
            {"weight_kg": float(s.weight_kg or 0), "reps": s.reps or 0, "rpe": float(s.rpe) if s.rpe else None}
            for s in sets_in_session
            if s.weight_kg is not None and s.reps is not None
        ]
        all_time_records.extend(records)

        bs = best_set(records)
        best_set_payload = None
        if bs:
            best_set_payload = {
                "weight_kg": bs["weight_kg"],
                "reps": bs["reps"],
                "estimated_1rm_kg": epley(bs["weight_kg"], bs["reps"]),
            }

        history_entries.append(
            SessionHistoryEntry(
                session_id=sid,
                performed_at=session_times[sid],
                sets=[
                    {
                        "set_number": s.set_number,
                        "weight_kg": float(s.weight_kg) if s.weight_kg is not None else None,
                        "reps": s.reps,
                        "rpe": float(s.rpe) if s.rpe is not None else None,
                    }
                    for s in sorted(sets_in_session, key=lambda x: x.set_number)
                ],
                best_set=best_set_payload,
            )
        )

    all_time_bs = best_set(all_time_records)
    all_time_best = None
    if all_time_bs:
        all_time_best = {
            "weight_kg": all_time_bs["weight_kg"],
            "reps": all_time_bs["reps"],
            "estimated_1rm_kg": epley(all_time_bs["weight_kg"], all_time_bs["reps"]),
        }

    return ExerciseHistoryResponse(
        canonical_exercise_id=canonical_id,
        canonical_name=canonical_name,
        sessions=history_entries,
        all_time_best=all_time_best,
    )


async def create_cardio_log(
    db: AsyncSession,
    user_id: UUID,
    prep_id: UUID,
    data: CardioLogCreate,
) -> CardioLog:
    log = CardioLog(
        user_id=user_id,
        prep_id=prep_id,
        performed_at=data.performed_at,
        modality=data.modality,
        duration_min=data.duration_min,
        avg_hr=data.avg_hr,
        calories_burned_estimate=data.calories_burned_estimate,
        notes=data.notes,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log
