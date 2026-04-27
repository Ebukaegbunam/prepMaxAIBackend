from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    workout_day_id: UUID | None = None
    started_at: datetime
    title: str | None = None


class SessionPatch(BaseModel):
    completed_at: datetime | None = None
    notes: str | None = None
    title: str | None = None


class SessionResponse(BaseModel):
    id: UUID
    prep_id: UUID
    workout_day_id: UUID | None
    title: str | None
    started_at: datetime
    completed_at: datetime | None
    notes: str | None
    set_count: int = 0
    total_volume_kg: float = 0.0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SetCreate(BaseModel):
    exercise_id: UUID | None = None
    exercise_name_raw: str
    set_number: int = Field(default=1, ge=1)
    weight_kg: float | None = Field(default=None, ge=0)
    reps: int | None = Field(default=None, ge=0)
    rpe: float | None = Field(default=None, ge=0, le=10)
    performed_at: datetime | None = None
    notes: str | None = None


class SetPatch(BaseModel):
    weight_kg: float | None = Field(default=None, ge=0)
    reps: int | None = Field(default=None, ge=0)
    rpe: float | None = Field(default=None, ge=0, le=10)
    notes: str | None = None


class SetResponse(BaseModel):
    id: UUID
    workout_session_id: UUID
    exercise_id: UUID | None
    canonical_exercise_id: UUID | None
    exercise_name_raw: str
    set_number: int
    weight_kg: float | None
    reps: int | None
    rpe: float | None
    performed_at: datetime
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CardioLogCreate(BaseModel):
    performed_at: datetime
    modality: str
    duration_min: int | None = Field(default=None, ge=0)
    avg_hr: int | None = Field(default=None, ge=0)
    calories_burned_estimate: int | None = Field(default=None, ge=0)
    notes: str | None = None


class CardioLogResponse(BaseModel):
    id: UUID
    prep_id: UUID
    performed_at: datetime
    modality: str
    duration_min: int | None
    avg_hr: int | None
    calories_burned_estimate: int | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BestSet(BaseModel):
    weight_kg: float
    reps: int
    estimated_1rm_kg: float


class SessionHistoryEntry(BaseModel):
    session_id: UUID
    performed_at: datetime
    sets: list[dict]
    best_set: BestSet | None


class ExerciseHistoryResponse(BaseModel):
    canonical_exercise_id: UUID
    canonical_name: str
    sessions: list[SessionHistoryEntry]
    all_time_best: BestSet | None
