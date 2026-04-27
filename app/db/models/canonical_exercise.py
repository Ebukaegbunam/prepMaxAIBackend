import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CanonicalExercise(Base):
    __tablename__ = "canonical_exercise"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    primary_muscles: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    equipment: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_user_created: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    aliases: Mapped[list["ExerciseAlias"]] = relationship(back_populates="canonical_exercise", lazy="selectin")  # type: ignore[name-defined]
