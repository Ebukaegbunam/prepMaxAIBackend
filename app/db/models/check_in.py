import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CheckIn(Base):
    __tablename__ = "check_in"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prep_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prep.id", ondelete="CASCADE"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    mood: Mapped[int | None] = mapped_column(Integer)
    energy: Mapped[int | None] = mapped_column(Integer)
    sleep: Mapped[int | None] = mapped_column(Integer)
    training_quality: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    measurement_log_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("measurement_log.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
