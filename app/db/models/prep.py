import uuid
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Prep(Base):
    __tablename__ = "prep"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    division: Mapped[str] = mapped_column(String(40), nullable=False)
    prep_length_weeks: Mapped[int] = mapped_column(Integer, nullable=False, server_default="16")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    target_competition_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    starting_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    target_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    starting_bf_pct: Mapped[float | None] = mapped_column(Numeric(4, 1))
    target_bf_pct: Mapped[float | None] = mapped_column(Numeric(4, 1))
    phase_split: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default='{"maintenance_weeks": 4, "cut_weeks": 12}'
    )
    current_workout_template_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    current_weekly_plan_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    completion_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
