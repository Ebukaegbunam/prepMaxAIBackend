import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Photo(Base):
    __tablename__ = "photo"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prep_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prep.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(Text)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    week_number: Mapped[int | None] = mapped_column(Integer)
    angle: Mapped[str | None] = mapped_column(Text)
    body_part: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
