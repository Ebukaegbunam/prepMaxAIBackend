import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WorkoutDay(Base):
    __tablename__ = "workout_day"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    workout_template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workout_template.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    template: Mapped["WorkoutTemplate"] = relationship(back_populates="days")  # type: ignore[name-defined]
    exercises: Mapped[list["Exercise"]] = relationship(back_populates="day", lazy="selectin", cascade="all, delete-orphan", order_by="Exercise.order")  # type: ignore[name-defined]
