"""Detected anomalies and their supporting evidence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Double, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base

if TYPE_CHECKING:
    from app.domain.alert import Alert
    from app.domain.detection_config import DetectionConfig


class Detection(Base):
    __tablename__ = "detections"
    __table_args__ = (
        CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="detections_severity_check"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="detections_confidence_check"),
    )

    detection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    configuration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("detection_configs.configuration_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    first_ingested_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Double, nullable=False)
    src_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    dst_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    src_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(Text, nullable=True)
    window_size_s: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    configuration: Mapped[DetectionConfig] = relationship(back_populates="detections")
    alert: Mapped[Alert | None] = relationship(back_populates="detection")
