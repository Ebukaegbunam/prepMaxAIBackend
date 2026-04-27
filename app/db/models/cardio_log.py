import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CardioLog(Base):
    __tablename__ = "cardio_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prep_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("prep.id", ondelete="CASCADE"),
        nullable=False,
    )
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    modality: Mapped[str] = mapped_column(Text, nullable=False)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    calories_burned_estimate: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
