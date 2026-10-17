"""Operator-facing alerts generated from detections."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base

if TYPE_CHECKING:
    from app.domain.detection import Detection


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    detection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("detections.detection_id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    detection: Mapped[Detection] = relationship(back_populates="alert")
