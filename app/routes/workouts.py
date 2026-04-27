"""Workout template, day, and exercise routes."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_jwt import AuthUser, get_current_user
from app.db.session import get_db
from app.schemas.workout import (
    CanonicalExerciseCreate, CanonicalExerciseResponse, CanonicalizePreflight,
    ExerciseCreate, ExercisePatch, ExerciseReorder, ExerciseResponse,
    WorkoutDayCreate, WorkoutDayPatch, WorkoutDayResponse,
    WorkoutTemplateCreate, WorkoutTemplatePatch, WorkoutTemplateResponse,
)
from app.services import canonicalization, workout_service

router = APIRouter(tags=["workouts"])


def _exercise_response(exercise, alternatives: list | None = None) -> ExerciseResponse:
    canon_name = None
    if exercise.canonical_exercise:
        canon_name = exercise.canonical_exercise.name
    return ExerciseResponse(
        id=exercise.id,
        workout_day_id=exercise.workout_day_id,
        order=exercise.order,
        canonical_exercise_id=exercise.canonical_exercise_id,
        canonical_name=canon_name,
        raw_name=exercise.raw_name,
        name_match_confidence=exercise.name_match_confidence,
        target_sets=exercise.target_sets,
        target_reps=exercise.target_reps,
        target_weight_kg=float(exercise.target_weight_kg) if exercise.target_weight_kg else None,
        rest_seconds=exercise.rest_seconds,
        notes=exercise.notes,
        suggestions=alternatives or [],
    )


# ── Canonical exercises ──────────────────────────────────────────────────────

@router.get("/canonical-exercises", response_model=list[CanonicalExerciseResponse])
async def search_canonical_exercises(
    q: str = "",
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CanonicalExerciseResponse]:
    exercises = await workout_service.search_canonical(q, db)
    return [
        CanonicalExerciseResponse(
            id=ex.id, name=ex.name, category=ex.category,
            primary_muscles=ex.primary_muscles,
            equipment=ex.equipment,
            is_user_created=ex.is_user_created,
            common_aliases=[a.alias for a in (ex.aliases or [])[:5]],
        )
        for ex in exercises
    ]


@router.post("/canonical-exercises", response_model=CanonicalExerciseResponse, status_code=201)
async def create_canonical_exercise(
    body: CanonicalExerciseCreate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CanonicalExerciseResponse:
    ce = await workout_service.create_canonical_exercise(body.name, body.category, UUID(user.id), db)
    return CanonicalExerciseResponse(
        id=ce.id, name=ce.name, category=ce.category,
        primary_muscles=ce.primary_muscles,
        equipment=ce.equipment,
        is_user_created=ce.is_user_created,
    )


@router.post("/ai/canonicalize-exercise")
async def canonicalize_exercise(
    body: CanonicalizePreflight,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    match = await canonicalization.resolve(body.name, db, UUID(user.id))
    result = None
    if match.canonical_exercise_id:
        result = {
            "canonical_exercise_id": str(match.canonical_exercise_id),
            "canonical_name": match.canonical_name,
            "confidence": match.confidence,
            "via": match.via,
        }
    return {"match": result, "alternatives": match.alternatives}


# ── Workout templates ────────────────────────────────────────────────────────

@router.post("/preps/{prep_id}/workout-templates", response_model=WorkoutTemplateResponse, status_code=201)
async def create_workout_template(
    prep_id: UUID,
    body: WorkoutTemplateCreate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutTemplateResponse:
    data = body.model_dump()
    template = await workout_service.create_template(prep_id, UUID(user.id), data, db)
    return WorkoutTemplateResponse.model_validate(template)


@router.get("/workout-templates/{template_id}", response_model=WorkoutTemplateResponse)
async def get_workout_template(
    template_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutTemplateResponse:
    template = await workout_service.get_template(template_id, UUID(user.id), db)
    if template is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Template not found"}})
    return WorkoutTemplateResponse.model_validate(template)


@router.patch("/workout-templates/{template_id}", response_model=WorkoutTemplateResponse)
async def patch_workout_template(
    template_id: UUID,
    body: WorkoutTemplatePatch,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutTemplateResponse:
    template = await workout_service.get_template(template_id, UUID(user.id), db)
    if template is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Template not found"}})
    updates = body.model_dump(exclude_unset=True)
    template = await workout_service.patch_template(template, updates, db)
    return WorkoutTemplateResponse.model_validate(template)


# ── Workout days ─────────────────────────────────────────────────────────────

@router.post("/workout-templates/{template_id}/days", response_model=WorkoutDayResponse, status_code=201)
async def add_workout_day(
    template_id: UUID,
    body: WorkoutDayCreate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutDayResponse:
    day = await workout_service.add_day(template_id, UUID(user.id), body.model_dump(), db)
    return WorkoutDayResponse(
        id=day.id, workout_template_id=day.workout_template_id,
        day_of_week=day.day_of_week, title=day.title, notes=day.notes,
        exercises=[], created_at=day.created_at, updated_at=day.updated_at,
    )


@router.patch("/workout-days/{day_id}", response_model=WorkoutDayResponse)
async def patch_workout_day(
    day_id: UUID,
    body: WorkoutDayPatch,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutDayResponse:
    day = await workout_service.get_day(day_id, UUID(user.id), db)
    if day is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Day not found"}})
    updates = body.model_dump(exclude_unset=True)
    day = await workout_service.patch_day(day, updates, db)
    return WorkoutDayResponse(
        id=day.id, workout_template_id=day.workout_template_id,
        day_of_week=day.day_of_week, title=day.title, notes=day.notes,
        exercises=[_exercise_response(e) for e in (day.exercises or [])],
        created_at=day.created_at, updated_at=day.updated_at,
    )


@router.delete("/workout-days/{day_id}", status_code=204)
async def delete_workout_day(
    day_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    day = await workout_service.get_day(day_id, UUID(user.id), db)
    if day is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Day not found"}})
    await workout_service.delete_day(day, db)


# ── Exercises ────────────────────────────────────────────────────────────────

@router.post("/workout-days/{day_id}/exercises", response_model=ExerciseResponse, status_code=201)
async def add_exercise(
    day_id: UUID,
    body: ExerciseCreate,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExerciseResponse:
    raw_name = body.name
    data = body.model_dump(exclude={"name"})
    exercise, alternatives = await workout_service.add_exercise(day_id, UUID(user.id), raw_name, data, db)
    return _exercise_response(exercise, alternatives)


@router.patch("/exercises/{exercise_id}", response_model=ExerciseResponse)
async def patch_exercise(
    exercise_id: UUID,
    body: ExercisePatch,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExerciseResponse:
    exercise = await workout_service.get_exercise(exercise_id, UUID(user.id), db)
    if exercise is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Exercise not found"}})
    updates = body.model_dump(exclude_unset=True)
    exercise, alternatives = await workout_service.patch_exercise(exercise, updates, db)
    return _exercise_response(exercise, alternatives)


@router.delete("/exercises/{exercise_id}", status_code=204)
async def delete_exercise(
    exercise_id: UUID,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    exercise = await workout_service.get_exercise(exercise_id, UUID(user.id), db)
    if exercise is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Exercise not found"}})
    await workout_service.delete_exercise(exercise, db)


@router.post("/exercises/{exercise_id}/reorder", status_code=204)
async def reorder_exercise(
    exercise_id: UUID,
    body: ExerciseReorder,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    exercise = await workout_service.get_exercise(exercise_id, UUID(user.id), db)
    if exercise is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Exercise not found"}})
    await workout_service.reorder_exercise(exercise, body.new_order, db)
