from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.meal_log import MealLog
from app.db.models.meal_plan import MealPlan
from app.db.models.prep import Prep
from app.db.models.profile import Profile
from app.db.models.weekly_plan import WeeklyPlan
from app.lib import calorie_engine
from app.schemas.meal import (
    DailyMealLogResponse,
    MealLogCreate,
    MealLogPatch,
    MealPlanCreate,
    MealPlanPatch,
    MealLogResponse,
)


def _compute_week_number(start_date: date, for_date: date) -> int:
    delta = (for_date - start_date).days
    return max(1, delta // 7 + 1)


async def _get_profile(db: AsyncSession, user_id: UUID) -> Profile | None:
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    return result.scalar_one_or_none()


async def generate_weekly_plan(
    db: AsyncSession,
    user_id: UUID,
    prep: Prep,
) -> list[dict[str, Any]]:
    profile = await _get_profile(db, user_id)

    weight_kg = float(prep.starting_weight_kg or 80)
    height_cm = float(profile.height_cm or 175) if profile else 175
    age = int(profile.age or 25) if profile else 25
    sex = (profile.sex or "male") if profile else "male"
    training_days = int(profile.training_days_per_week or 5) if profile else 5
    maintenance_weeks = prep.phase_split.get("maintenance_weeks", 4)

    bmr_val = calorie_engine.bmr(weight_kg, height_cm, age, sex)
    tdee_val = calorie_engine.tdee(bmr_val, training_days)

    week_targets = []
    for w in range(1, prep.prep_length_weeks + 1):
        targets = calorie_engine.targets_for_week(
            prep_length_weeks=prep.prep_length_weeks,
            week_number=w,
            maintenance_weeks=maintenance_weeks,
            tdee_kcal=tdee_val,
            weight_kg=weight_kg,
        )
        phase = "maintenance" if w <= maintenance_weeks else "cut"
        week_targets.append({"week_number": w, "phase": phase, "targets": dict(targets)})
    return week_targets


async def get_or_create_weekly_plan(
    db: AsyncSession,
    user_id: UUID,
    prep_id: UUID,
    week_number: int,
    targets: dict[str, Any],
) -> WeeklyPlan:
    result = await db.execute(
        select(WeeklyPlan).where(
            WeeklyPlan.prep_id == prep_id,
            WeeklyPlan.week_number == week_number,
        )
    )
    plan = result.scalar_one_or_none()
    if plan:
        plan.targets = targets
    else:
        plan = WeeklyPlan(
            user_id=user_id,
            prep_id=prep_id,
            week_number=week_number,
            targets=targets,
        )
        db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def list_weekly_plans(
    db: AsyncSession, user_id: UUID, prep_id: UUID
) -> list[WeeklyPlan]:
    result = await db.execute(
        select(WeeklyPlan)
        .where(WeeklyPlan.prep_id == prep_id, WeeklyPlan.user_id == user_id)
        .order_by(WeeklyPlan.week_number)
    )
    return list(result.scalars().all())


async def get_weekly_plan(
    db: AsyncSession, user_id: UUID, prep_id: UUID, week_number: int
) -> WeeklyPlan | None:
    result = await db.execute(
        select(WeeklyPlan).where(
            WeeklyPlan.prep_id == prep_id,
            WeeklyPlan.user_id == user_id,
            WeeklyPlan.week_number == week_number,
        )
    )
    return result.scalar_one_or_none()


async def create_meal_plan(
    db: AsyncSession, user_id: UUID, prep_id: UUID, data: MealPlanCreate
) -> MealPlan:
    result = await db.execute(
        select(MealPlan).where(
            MealPlan.prep_id == prep_id,
            MealPlan.week_number == data.week_number,
            MealPlan.day_of_week == data.day_of_week,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.slots = data.slots
        existing.targets = data.targets
        await db.commit()
        await db.refresh(existing)
        return existing

    plan = MealPlan(
        user_id=user_id,
        prep_id=prep_id,
        weekly_plan_id=data.weekly_plan_id,
        week_number=data.week_number,
        day_of_week=data.day_of_week,
        targets=data.targets,
        slots=data.slots,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_meal_plan(db: AsyncSession, meal_plan_id: UUID, user_id: UUID) -> MealPlan | None:
    result = await db.execute(
        select(MealPlan).where(MealPlan.id == meal_plan_id, MealPlan.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def patch_meal_plan(db: AsyncSession, plan: MealPlan, data: MealPlanPatch) -> MealPlan:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return plan


async def create_meal_log(
    db: AsyncSession, user_id: UUID, prep_id: UUID, data: MealLogCreate
) -> MealLog:
    log = MealLog(
        user_id=user_id,
        prep_id=prep_id,
        eaten_at=data.eaten_at,
        slot=data.slot,
        name=data.name,
        calories=data.calories,
        protein_g=data.protein_g,
        carbs_g=data.carbs_g,
        fat_g=data.fat_g,
        source=data.source,
        linked_meal_plan_id=data.linked_meal_plan_id,
        notes=data.notes,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_meal_log(db: AsyncSession, log_id: UUID, user_id: UUID) -> MealLog | None:
    result = await db.execute(
        select(MealLog).where(MealLog.id == log_id, MealLog.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def patch_meal_log(db: AsyncSession, log: MealLog, data: MealLogPatch) -> MealLog:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(log, field, value)
    await db.commit()
    await db.refresh(log)
    return log


async def delete_meal_log(db: AsyncSession, log: MealLog) -> None:
    await db.delete(log)
    await db.commit()


async def get_daily_meal_logs(
    db: AsyncSession,
    user_id: UUID,
    prep_id: UUID,
    for_date: date,
    targets: dict[str, Any],
) -> DailyMealLogResponse:
    day_start = datetime(for_date.year, for_date.month, for_date.day, tzinfo=timezone.utc)
    day_end = datetime(for_date.year, for_date.month, for_date.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await db.execute(
        select(MealLog).where(
            MealLog.user_id == user_id,
            MealLog.prep_id == prep_id,
            MealLog.eaten_at >= day_start,
            MealLog.eaten_at <= day_end,
        ).order_by(MealLog.eaten_at)
    )
    logs = list(result.scalars().all())

    totals: dict[str, float] = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
    for log in logs:
        totals["calories"] += float(log.calories or 0)
        totals["protein_g"] += float(log.protein_g or 0)
        totals["carbs_g"] += float(log.carbs_g or 0)
        totals["fat_g"] += float(log.fat_g or 0)

    remaining = {
        "calories": max(0, float(targets.get("calories", 0)) - totals["calories"]),
        "protein_g": max(0, float(targets.get("protein_g", 0)) - totals["protein_g"]),
        "carbs_g": max(0, float(targets.get("carbs_g", 0)) - totals["carbs_g"]),
        "fat_g": max(0, float(targets.get("fat_g", 0)) - totals["fat_g"]),
    }

    return DailyMealLogResponse(
        date=for_date.isoformat(),
        totals=totals,
        targets=targets,
        remaining=remaining,
        logs=[MealLogResponse.model_validate(log) for log in logs],
    )
