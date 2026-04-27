from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MacroTargets(BaseModel):
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int


class WeeklyPlanResponse(BaseModel):
    id: UUID
    prep_id: UUID
    week_number: int
    targets: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MealPlanCreate(BaseModel):
    week_number: int = Field(ge=1)
    day_of_week: int = Field(ge=1, le=7)
    targets: dict[str, Any] = {}
    slots: list[Any] = []
    weekly_plan_id: UUID | None = None


class MealPlanPatch(BaseModel):
    slots: list[Any] | None = None
    targets: dict[str, Any] | None = None


class MealPlanResponse(BaseModel):
    id: UUID
    prep_id: UUID
    weekly_plan_id: UUID | None
    week_number: int
    day_of_week: int
    targets: dict[str, Any]
    slots: list[Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MealLogCreate(BaseModel):
    eaten_at: datetime
    slot: str | None = None
    name: str
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    source: str = "freeform"
    linked_meal_plan_id: UUID | None = None
    notes: str | None = None


class MealLogPatch(BaseModel):
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    notes: str | None = None


class MealLogResponse(BaseModel):
    id: UUID
    prep_id: UUID
    eaten_at: datetime
    slot: str | None
    name: str
    calories: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    source: str
    linked_meal_plan_id: UUID | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DailyMealLogResponse(BaseModel):
    date: str
    totals: dict[str, float]
    targets: dict[str, Any]
    remaining: dict[str, float]
    logs: list[MealLogResponse]


class GenerateDailyMealsRequest(BaseModel):
    prep_id: UUID
    week_number: int = Field(ge=1)
    day_of_week: int = Field(ge=1, le=7)
    schedule_hint: str | None = None
    pantry: list[str] = []
    carry_forward_from_day: int | None = None


class GenerateWeeklyMealsRequest(BaseModel):
    prep_id: UUID
    week_number: int = Field(ge=1)
    schedule_hint: str | None = None
    pantry: list[str] = []
    vary_by: str | None = None


class SwapMealRequest(BaseModel):
    prep_id: UUID
    current_meal: dict[str, Any]
    remaining_macros: dict[str, Any]
    context: str | None = None
    pantry: list[str] = []


class EstimateMacrosRequest(BaseModel):
    description: str


class RestaurantsNearRequest(BaseModel):
    lat: float
    lng: float
    radius_m: int = Field(default=1500, ge=100, le=50000)
    filter: str | None = None
    remaining_macros: dict[str, Any]
