import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedCompetition(Base):
    __tablename__ = "saved_competition"
    __table_args__ = (UniqueConstraint("user_id", "competition_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    competition_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("competition.id", ondelete="CASCADE"), nullable=False
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
