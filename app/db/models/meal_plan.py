import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MealPlan(Base):
    __tablename__ = "meal_plan"
    __table_args__ = (UniqueConstraint("prep_id", "week_number", "day_of_week"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prep_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("prep.id", ondelete="CASCADE"),
        nullable=False,
    )
    weekly_plan_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("weekly_plan.id", ondelete="SET NULL"),
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    targets: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    slots: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
