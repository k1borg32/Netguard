"""Stored detection settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base

if TYPE_CHECKING:
    from app.domain.detection import Detection


class DetectionConfig(Base):
    __tablename__ = "detection_configs"

    configuration_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    detection_type: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)

    detections: Mapped[list[Detection]] = relationship(back_populates="configuration")
