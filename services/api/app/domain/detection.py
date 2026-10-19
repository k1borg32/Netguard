"""Detected anomaly and its supporting evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from .alert import Alert
    from .detection_config import DetectionConfig


@dataclass(eq=False, kw_only=True)
class Detection:
    detection_id: UUID
    created_at: datetime
    type: str
    method: str
    severity: str
    configuration_id: UUID | None = None
    first_ingested_at: datetime | None = None
    confidence: float | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str | None = None
    window_size_s: int | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    explanation: str | None = None
    features: dict[str, Any] | None = None
    trace_ids: list[str] = field(default_factory=list)
    configuration: DetectionConfig | None = field(default=None, init=False, repr=False)
    alert: Alert | None = field(default=None, init=False, repr=False)
