import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeightLog(Base):
    __tablename__ = "weight_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prep_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prep.id", ondelete="CASCADE"), nullable=False
    )
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
