import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SetLog(Base):
    __tablename__ = "set_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    workout_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workout_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("exercise.id", ondelete="SET NULL"),
    )
    canonical_exercise_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_exercise.id", ondelete="SET NULL"),
    )
    exercise_name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    reps: Mapped[int | None] = mapped_column(Integer)
    rpe: Mapped[float | None] = mapped_column(Numeric(3, 1))
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["WorkoutSession"] = relationship(back_populates="sets")  # type: ignore[name-defined]
