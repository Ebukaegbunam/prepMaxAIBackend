"""Workout template, day, and exercise CRUD service."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.canonical_exercise import CanonicalExercise
from app.db.models.workout_day import WorkoutDay
from app.db.models.workout_exercise import Exercise
from app.db.models.workout_template import WorkoutTemplate
from app.services.canonicalization import resolve


async def get_template(template_id: UUID, user_id: UUID, db: AsyncSession) -> WorkoutTemplate | None:
    result = await db.execute(
        select(WorkoutTemplate)
        .options(selectinload(WorkoutTemplate.days).selectinload(WorkoutDay.exercises))
        .where(WorkoutTemplate.id == template_id, WorkoutTemplate.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_template(
    prep_id: UUID,
    user_id: UUID,
    data: dict,
    db: AsyncSession,
) -> WorkoutTemplate:
    days_data = data.pop("days", [])
    template = WorkoutTemplate(prep_id=prep_id, user_id=user_id, **data)
    db.add(template)
    await db.flush()

    for day_data in days_data:
        exercises_data = day_data.pop("exercises", [])
        day = WorkoutDay(workout_template_id=template.id, user_id=user_id, **day_data)
        db.add(day)
        await db.flush()
        for ex_data in exercises_data:
            match = await resolve(ex_data.get("raw_name", ""), db, user_id)
            exercise = Exercise(
                workout_day_id=day.id,
                user_id=user_id,
                canonical_exercise_id=match.canonical_exercise_id,
                name_match_confidence=match.confidence,
                **ex_data,
            )
            db.add(exercise)

    await db.commit()
    result = await db.execute(
        select(WorkoutTemplate)
        .options(selectinload(WorkoutTemplate.days).selectinload(WorkoutDay.exercises))
        .where(WorkoutTemplate.id == template.id)
    )
    return result.scalar_one()


async def patch_template(template: WorkoutTemplate, updates: dict, db: AsyncSession) -> WorkoutTemplate:
    for key, value in updates.items():
        setattr(template, key, value)
    await db.commit()
    await db.refresh(template)
    return template


async def add_day(
    template_id: UUID,
    user_id: UUID,
    data: dict,
    db: AsyncSession,
) -> WorkoutDay:
    day = WorkoutDay(workout_template_id=template_id, user_id=user_id, **data)
    db.add(day)
    await db.commit()
    await db.refresh(day)
    return day


async def get_day(day_id: UUID, user_id: UUID, db: AsyncSession) -> WorkoutDay | None:
    result = await db.execute(
        select(WorkoutDay).where(WorkoutDay.id == day_id, WorkoutDay.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def patch_day(day: WorkoutDay, updates: dict, db: AsyncSession) -> WorkoutDay:
    for key, value in updates.items():
        setattr(day, key, value)
    await db.commit()
    await db.refresh(day)
    return day


async def delete_day(day: WorkoutDay, db: AsyncSession) -> None:
    await db.delete(day)
    await db.commit()


async def add_exercise(
    day_id: UUID,
    user_id: UUID,
    raw_name: str,
    data: dict,
    db: AsyncSession,
) -> tuple[Exercise, list[dict]]:
    match = await resolve(raw_name, db, user_id)
    exercise = Exercise(
        workout_day_id=day_id,
        user_id=user_id,
        raw_name=raw_name,
        canonical_exercise_id=match.canonical_exercise_id,
        name_match_confidence=match.confidence,
        **data,
    )
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    return exercise, match.alternatives


async def get_exercise(exercise_id: UUID, user_id: UUID, db: AsyncSession) -> Exercise | None:
    result = await db.execute(
        select(Exercise).where(Exercise.id == exercise_id, Exercise.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def patch_exercise(exercise: Exercise, updates: dict, db: AsyncSession) -> tuple[Exercise, list[dict]]:
    alternatives: list[dict] = []
    if "name" in updates:
        raw_name = updates.pop("name")
        exercise.raw_name = raw_name
        match = await resolve(raw_name, db, exercise.user_id)
        exercise.canonical_exercise_id = match.canonical_exercise_id
        exercise.name_match_confidence = match.confidence
        alternatives = match.alternatives

    for key, value in updates.items():
        setattr(exercise, key, value)

    await db.commit()
    await db.refresh(exercise)
    return exercise, alternatives


async def delete_exercise(exercise: Exercise, db: AsyncSession) -> None:
    await db.delete(exercise)
    await db.commit()


async def reorder_exercise(exercise: Exercise, new_order: int, db: AsyncSession) -> None:
    exercise.order = new_order
    await db.commit()


async def search_canonical(q: str, db: AsyncSession, limit: int = 20) -> list[CanonicalExercise]:
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT id FROM canonical_exercise
            WHERE similarity(lower(name), lower(:q)) > 0.2
               OR lower(name) LIKE lower(:like)
            ORDER BY similarity(lower(name), lower(:q)) DESC
            LIMIT :limit
        """),
        {"q": q, "like": f"%{q.lower()}%", "limit": limit},
    )
    ids = [r[0] for r in result.fetchall()]
    if not ids:
        return []
    result2 = await db.execute(
        select(CanonicalExercise).where(CanonicalExercise.id.in_(ids))
    )
    return list(result2.scalars().all())


async def create_canonical_exercise(
    name: str,
    category: str,
    user_id: UUID,
    db: AsyncSession,
) -> CanonicalExercise:
    ce = CanonicalExercise(
        name=name,
        category=category,
        is_user_created=True,
        created_by_user_id=user_id,
    )
    db.add(ce)
    await db.commit()
    await db.refresh(ce)
    return ce
