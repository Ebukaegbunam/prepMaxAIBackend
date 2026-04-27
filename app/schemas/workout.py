from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CanonicalExerciseResponse(BaseModel):
    id: UUID
    name: str
    category: str
    primary_muscles: list[str]
    equipment: list[str]
    is_user_created: bool
    common_aliases: list[str] = []

    model_config = {"from_attributes": True}


class ExerciseInTemplate(BaseModel):
    order: int = 0
    raw_name: str
    canonical_exercise_id: UUID | None = None
    target_sets: int | None = None
    target_reps: str | None = None
    target_weight_kg: float | None = None
    rest_seconds: int | None = None
    notes: str | None = None


class WorkoutDayInTemplate(BaseModel):
    day_of_week: int = Field(..., ge=1, le=7)
    title: str
    notes: str | None = None
    exercises: list[ExerciseInTemplate] = []


class WorkoutTemplateCreate(BaseModel):
    name: str
    notes: str | None = None
    based_on_parse_id: UUID | None = None
    days: list[WorkoutDayInTemplate] = []


class WorkoutTemplatePatch(BaseModel):
    name: str | None = None
    notes: str | None = None


class WorkoutDayCreate(BaseModel):
    day_of_week: int = Field(..., ge=1, le=7)
    title: str
    notes: str | None = None


class WorkoutDayPatch(BaseModel):
    day_of_week: int | None = Field(None, ge=1, le=7)
    title: str | None = None
    notes: str | None = None


class ExerciseCreate(BaseModel):
    name: str
    target_sets: int | None = None
    target_reps: str | None = None
    target_weight_kg: float | None = None
    rest_seconds: int | None = None
    notes: str | None = None
    order: int = 0


class ExercisePatch(BaseModel):
    name: str | None = None
    target_sets: int | None = None
    target_reps: str | None = None
    target_weight_kg: float | None = None
    rest_seconds: int | None = None
    notes: str | None = None


class ExerciseReorder(BaseModel):
    new_order: int


class ExerciseResponse(BaseModel):
    id: UUID
    workout_day_id: UUID
    order: int
    canonical_exercise_id: UUID | None
    canonical_name: str | None
    raw_name: str
    name_match_confidence: str | None
    target_sets: int | None
    target_reps: str | None
    target_weight_kg: float | None
    rest_seconds: int | None
    notes: str | None
    suggestions: list[dict[str, Any]] = []

    model_config = {"from_attributes": True}


class WorkoutDayResponse(BaseModel):
    id: UUID
    workout_template_id: UUID
    day_of_week: int
    title: str
    notes: str | None
    exercises: list[ExerciseResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkoutTemplateResponse(BaseModel):
    id: UUID
    prep_id: UUID
    name: str
    notes: str | None
    days: list[WorkoutDayResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ParseWorkoutRequest(BaseModel):
    prep_id: UUID
    text: str
    division: str | None = None


class CanonicalizePreflight(BaseModel):
    name: str


class CanonicalExerciseCreate(BaseModel):
    name: str
    category: str
