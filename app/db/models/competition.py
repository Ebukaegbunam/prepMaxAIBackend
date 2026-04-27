import uuid
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Competition(Base):
    __tablename__ = "competition"
    __table_args__ = (UniqueConstraint("name", "date", "federation"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    federation: Mapped[str] = mapped_column(String(50), nullable=False)
    tested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    city: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(String(10), nullable=False, server_default="US")
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6))
    divisions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    registration_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
