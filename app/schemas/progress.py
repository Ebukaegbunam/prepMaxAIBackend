from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WeightLogCreate(BaseModel):
    logged_at: datetime | None = None
    weight_kg: float = Field(gt=0)
    source: str = "manual"
    notes: str | None = None


class WeightLogResponse(BaseModel):
    id: UUID
    prep_id: UUID
    logged_at: datetime
    weight_kg: float
    source: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WeightTrend(BaseModel):
    current_avg_7d: float | None
    previous_avg_7d: float | None
    delta_kg: float | None
    trajectory: str


class WeightLogListResponse(BaseModel):
    items: list[WeightLogResponse]
    trend: WeightTrend


class MeasurementLogCreate(BaseModel):
    logged_at: datetime | None = None
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None
    left_arm_cm: float | None = None
    right_arm_cm: float | None = None
    left_thigh_cm: float | None = None
    right_thigh_cm: float | None = None
    left_calf_cm: float | None = None
    right_calf_cm: float | None = None
    notes: str | None = None


class MeasurementLogResponse(BaseModel):
    id: UUID
    prep_id: UUID
    logged_at: datetime
    chest_cm: float | None
    waist_cm: float | None
    hips_cm: float | None
    left_arm_cm: float | None
    right_arm_cm: float | None
    left_thigh_cm: float | None
    right_thigh_cm: float | None
    left_calf_cm: float | None
    right_calf_cm: float | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PhotoRegisterRequest(BaseModel):
    storage_key: str
    taken_at: datetime
    week_number: int | None = None
    angle: str | None = None
    body_part: str | None = None


class PhotoResponse(BaseModel):
    id: UUID
    prep_id: UUID
    storage_key: str
    thumbnail_key: str | None
    taken_at: datetime
    week_number: int | None
    angle: str | None
    body_part: str | None
    url: str | None = None
    thumbnail_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckInCreate(BaseModel):
    week_number: int = Field(ge=1)
    completed_at: datetime
    weight_kg: float | None = Field(default=None, gt=0)
    mood: int | None = Field(default=None, ge=1, le=5)
    energy: int | None = Field(default=None, ge=1, le=5)
    sleep: int | None = Field(default=None, ge=1, le=5)
    training_quality: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    measurement_log_id: UUID | None = None
    photo_ids: list[UUID] = []


class CheckInResponse(BaseModel):
    id: UUID
    prep_id: UUID
    week_number: int
    completed_at: datetime
    weight_kg: float | None
    mood: int | None
    energy: int | None
    sleep: int | None
    training_quality: int | None
    notes: str | None
    measurement_log_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AiReportResponse(BaseModel):
    id: UUID
    prep_id: UUID
    week_number: int
    content: dict[str, Any]
    ai_request_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UploadUrlRequest(BaseModel):
    kind: str = "photo"
    content_type: str = "image/jpeg"
    size_bytes: int = Field(gt=0)
    prep_id: UUID


class ComparePhotosRequest(BaseModel):
    prep_id: UUID
    photo_a_id: UUID
    photo_b_id: UUID
    body_part: str | None = None
    force_regenerate: bool = False


class WeeklyReportRequest(BaseModel):
    force_regenerate: bool = False
