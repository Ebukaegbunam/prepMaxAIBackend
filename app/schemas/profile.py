from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    age: int | None = None
    sex: Literal["male", "female", "other"] | None = None
    height_cm: float | None = None
    units_weight: Literal["lb", "kg"] = "lb"
    units_measurement: Literal["in", "cm"] = "in"
    dietary_restrictions: list[str] = []
    loved_foods: list[str] = []
    hated_foods: list[str] = []
    cooking_skill: Literal["beginner", "intermediate", "advanced"] | None = None
    kitchen_equipment: list[str] = []
    job_type: str | None = None
    work_hours: str | None = None
    stress_level: Literal["low", "moderate", "high"] | None = None
    sleep_window: str | None = None
    preferred_training_time: Literal["morning", "midday", "afternoon", "evening"] | None = None
    training_days_per_week: int | None = Field(None, ge=1, le=7)
    narrative: str | None = None
    narrative_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileInitializeRequest(BaseModel):
    name: str
    age: int | None = None
    sex: Literal["male", "female", "other"] | None = None
    height_cm: float | None = None
    units_weight: Literal["lb", "kg"] = "lb"
    units_measurement: Literal["in", "cm"] = "in"
    dietary_restrictions: list[str] = []
    loved_foods: list[str] = []
    hated_foods: list[str] = []
    cooking_skill: Literal["beginner", "intermediate", "advanced"] | None = None
    kitchen_equipment: list[str] = []
    job_type: str | None = None
    work_hours: str | None = None
    stress_level: Literal["low", "moderate", "high"] | None = None
    sleep_window: str | None = None
    preferred_training_time: Literal["morning", "midday", "afternoon", "evening"] | None = None
    training_days_per_week: int | None = Field(None, ge=1, le=7)
    free_text_about_me: str | None = None


class ProfilePatchRequest(BaseModel):
    name: str | None = None
    age: int | None = None
    sex: Literal["male", "female", "other"] | None = None
    height_cm: float | None = None
    units_weight: Literal["lb", "kg"] | None = None
    units_measurement: Literal["in", "cm"] | None = None
    dietary_restrictions: list[str] | None = None
    loved_foods: list[str] | None = None
    hated_foods: list[str] | None = None
    cooking_skill: Literal["beginner", "intermediate", "advanced"] | None = None
    kitchen_equipment: list[str] | None = None
    job_type: str | None = None
    work_hours: str | None = None
    stress_level: Literal["low", "moderate", "high"] | None = None
    sleep_window: str | None = None
    preferred_training_time: Literal["morning", "midday", "afternoon", "evening"] | None = None
    training_days_per_week: int | None = Field(None, ge=1, le=7)
    free_text_update: str | None = None
