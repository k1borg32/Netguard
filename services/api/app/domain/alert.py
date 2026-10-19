"""Operator-facing alert generated from a detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from .detection import Detection


@dataclass(eq=False, kw_only=True)
class Alert:
    alert_id: UUID
    detection_id: UUID
    status: str
    created_at: datetime
    acknowledged_at: datetime | None = None
    detection: Detection = field(init=False, repr=False)
