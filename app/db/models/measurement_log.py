import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MeasurementLog(Base):
    __tablename__ = "measurement_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prep_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prep.id", ondelete="CASCADE"), nullable=False
    )
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    chest_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    waist_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    hips_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    left_arm_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    right_arm_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    left_thigh_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    right_thigh_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    left_calf_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    right_calf_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
