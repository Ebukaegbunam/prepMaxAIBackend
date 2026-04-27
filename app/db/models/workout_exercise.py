import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Exercise(Base):
    __tablename__ = "exercise"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    workout_day_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workout_day.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_exercise_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_exercise.id", ondelete="SET NULL"),
    )
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    target_sets: Mapped[int | None] = mapped_column(Integer)
    target_reps: Mapped[str | None] = mapped_column(String(20))
    target_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    rest_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    name_match_confidence: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    day: Mapped["WorkoutDay"] = relationship(back_populates="exercises")  # type: ignore[name-defined]
    canonical_exercise: Mapped["CanonicalExercise | None"] = relationship(lazy="selectin")  # type: ignore[name-defined]
