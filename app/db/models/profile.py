import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(10))
    height_cm: Mapped[float | None] = mapped_column(Float)
    units_weight: Mapped[str] = mapped_column(String(5), nullable=False, server_default="lb")
    units_measurement: Mapped[str] = mapped_column(String(5), nullable=False, server_default="in")
    dietary_restrictions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    loved_foods: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    hated_foods: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    cooking_skill: Mapped[str | None] = mapped_column(String(20))
    kitchen_equipment: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    job_type: Mapped[str | None] = mapped_column(Text)
    work_hours: Mapped[str | None] = mapped_column(String(50))
    stress_level: Mapped[str | None] = mapped_column(String(20))
    sleep_window: Mapped[str | None] = mapped_column(String(20))
    preferred_training_time: Mapped[str | None] = mapped_column(String(20))
    training_days_per_week: Mapped[int | None] = mapped_column(Integer)
    narrative: Mapped[str | None] = mapped_column(Text)
    narrative_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
