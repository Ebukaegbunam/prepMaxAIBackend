import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MealLog(Base):
    __tablename__ = "meal_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prep_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("prep.id", ondelete="CASCADE"),
        nullable=False,
    )
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    calories: Mapped[float | None] = mapped_column(Numeric(7, 2))
    protein_g: Mapped[float | None] = mapped_column(Numeric(6, 2))
    carbs_g: Mapped[float | None] = mapped_column(Numeric(6, 2))
    fat_g: Mapped[float | None] = mapped_column(Numeric(6, 2))
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="freeform")
    linked_meal_plan_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("meal_plan.id", ondelete="SET NULL"),
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
