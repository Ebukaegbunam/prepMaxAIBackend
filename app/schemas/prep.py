from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PrepCreate(BaseModel):
    division: Literal[
        "classic_physique", "men_physique", "women_physique",
        "bikini", "mens_open", "womens_figure",
    ]
    start_date: date
    prep_length_weeks: int = Field(16, ge=8, le=32)
    starting_weight_kg: float | None = None
    target_weight_kg: float | None = None
    starting_bf_pct: float | None = None
    target_bf_pct: float | None = None
    target_competition_id: UUID | None = None
    phase_split: dict[str, Any] = {"maintenance_weeks": 4, "cut_weeks": 12}


class PrepPatch(BaseModel):
    target_weight_kg: float | None = None
    target_bf_pct: float | None = None
    target_competition_id: UUID | None = None
    phase_split: dict[str, Any] | None = None
    status: Literal["active", "completed", "abandoned"] | None = None


class PrepCompleteRequest(BaseModel):
    completion_notes: str | None = None


class PrepResponse(BaseModel):
    id: UUID
    user_id: UUID
    division: str
    prep_length_weeks: int
    start_date: date
    target_date: date | None
    target_competition_id: UUID | None
    status: str
    starting_weight_kg: float | None
    target_weight_kg: float | None
    starting_bf_pct: float | None
    target_bf_pct: float | None
    phase_split: dict[str, Any]
    current_workout_template_id: UUID | None
    current_weekly_plan_id: UUID | None
    completion_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
