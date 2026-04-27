from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CompetitionResponse(BaseModel):
    id: UUID
    name: str
    date: date
    federation: str
    tested: bool
    city: str | None
    state: str | None
    country: str
    lat: float | None
    lng: float | None
    divisions: list[Any]
    registration_url: str | None
    refreshed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class SavedCompetitionCreate(BaseModel):
    competition_id: UUID


class SavedCompetitionResponse(BaseModel):
    id: UUID
    competition_id: UUID
    snapshot: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
