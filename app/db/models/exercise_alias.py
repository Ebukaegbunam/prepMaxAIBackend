import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

from app.db.base import Base


class ExerciseAlias(Base):
    __tablename__ = "exercise_alias"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_exercise_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_exercise.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    canonical_exercise: Mapped["CanonicalExercise"] = relationship(back_populates="aliases")  # type: ignore[name-defined]
