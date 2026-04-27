"""Meal plan, meal log, and weekly plan routes."""
from datetime import date
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_jwt import AuthUser, get_current_user
from app.db.session import get_db
from app.schemas.meal import (
    DailyMealLogResponse,
    MealLogCreate,
    MealLogPatch,
    MealLogResponse,
    MealPlanCreate,
    MealPlanPatch,
    MealPlanResponse,
    WeeklyPlanResponse,
)
from app.services import meal_service, prep_service

router = APIRouter(tags=["meals"])
log = structlog.get_logger()


@router.post("/preps/{prep_id}/weekly-plans/generate", response_model=list[dict])
async def generate_weekly_plan(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    return await meal_service.generate_weekly_plan(db, UUID(user.id), prep)


@router.get("/preps/{prep_id}/weekly-plans", response_model=list[WeeklyPlanResponse])
async def list_weekly_plans(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WeeklyPlanResponse]:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    plans = await meal_service.list_weekly_plans(db, UUID(user.id), prep_id)
    return [WeeklyPlanResponse.model_validate(p) for p in plans]


@router.get("/preps/{prep_id}/weekly-plans/{week_number}", response_model=WeeklyPlanResponse)
async def get_weekly_plan(
    prep_id: UUID,
    week_number: int,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeeklyPlanResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    plan = await meal_service.get_weekly_plan(db, UUID(user.id), prep_id, week_number)
    if plan is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Weekly plan not found"}})
    return WeeklyPlanResponse.model_validate(plan)


@router.post("/preps/{prep_id}/meal-plans", response_model=MealPlanResponse, status_code=201)
async def create_meal_plan(
    prep_id: UUID,
    body: MealPlanCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealPlanResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    plan = await meal_service.create_meal_plan(db, UUID(user.id), prep_id, body)
    return MealPlanResponse.model_validate(plan)


@router.get("/preps/{prep_id}/meal-plans", response_model=list[MealPlanResponse])
async def get_meal_plan_by_week_day(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    week: int | None = Query(default=None),
    day: int | None = Query(default=None),
) -> list[MealPlanResponse]:
    from sqlalchemy import select
    from app.db.models.meal_plan import MealPlan
    q = select(MealPlan).where(MealPlan.prep_id == prep_id, MealPlan.user_id == UUID(user.id))
    if week is not None:
        q = q.where(MealPlan.week_number == week)
    if day is not None:
        q = q.where(MealPlan.day_of_week == day)
    result = await db.execute(q.order_by(MealPlan.week_number, MealPlan.day_of_week))
    plans = list(result.scalars().all())
    return [MealPlanResponse.model_validate(p) for p in plans]


@router.patch("/meal-plans/{meal_plan_id}", response_model=MealPlanResponse)
async def patch_meal_plan(
    meal_plan_id: UUID,
    body: MealPlanPatch,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealPlanResponse:
    plan = await meal_service.get_meal_plan(db, meal_plan_id, UUID(user.id))
    if plan is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Meal plan not found"}})
    plan = await meal_service.patch_meal_plan(db, plan, body)
    return MealPlanResponse.model_validate(plan)


@router.post("/preps/{prep_id}/meal-logs", response_model=MealLogResponse, status_code=201)
async def create_meal_log(
    prep_id: UUID,
    body: MealLogCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealLogResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    meal_log = await meal_service.create_meal_log(db, UUID(user.id), prep_id, body)
    return MealLogResponse.model_validate(meal_log)


@router.get("/preps/{prep_id}/meal-logs", response_model=DailyMealLogResponse)
async def get_daily_meal_logs(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    for_date: date = Query(alias="date"),
) -> DailyMealLogResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    week_num = max(1, (for_date - prep.start_date).days // 7 + 1)
    maintenance_weeks = prep.phase_split.get("maintenance_weeks", 4)
    weight_kg = float(prep.starting_weight_kg or 80)

    from app.services.meal_service import _get_profile
    from app.lib import calorie_engine
    profile = await _get_profile(db, UUID(user.id))
    height_cm = float(profile.height_cm or 175) if profile else 175
    age = int(profile.age or 25) if profile else 25
    sex = (profile.sex or "male") if profile else "male"
    training_days = int(profile.training_days_per_week or 5) if profile else 5

    bmr_val = calorie_engine.bmr(weight_kg, height_cm, age, sex)
    tdee_val = calorie_engine.tdee(bmr_val, training_days)
    targets = calorie_engine.targets_for_week(
        prep_length_weeks=prep.prep_length_weeks,
        week_number=week_num,
        maintenance_weeks=maintenance_weeks,
        tdee_kcal=tdee_val,
        weight_kg=weight_kg,
    )

    return await meal_service.get_daily_meal_logs(
        db, UUID(user.id), prep_id, for_date, dict(targets)
    )


@router.patch("/meal-logs/{log_id}", response_model=MealLogResponse)
async def patch_meal_log(
    log_id: UUID,
    body: MealLogPatch,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MealLogResponse:
    meal_log = await meal_service.get_meal_log(db, log_id, UUID(user.id))
    if meal_log is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Meal log not found"}})
    meal_log = await meal_service.patch_meal_log(db, meal_log, body)
    return MealLogResponse.model_validate(meal_log)


@router.delete("/meal-logs/{log_id}", status_code=204)
async def delete_meal_log(
    log_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    meal_log = await meal_service.get_meal_log(db, log_id, UUID(user.id))
    if meal_log is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Meal log not found"}})
    await meal_service.delete_meal_log(db, meal_log)
