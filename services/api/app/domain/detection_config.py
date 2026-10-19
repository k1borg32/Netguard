"""Stored detection settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from .detection import Detection


@dataclass(eq=False, kw_only=True)
class DetectionConfig:
    configuration_id: UUID
    detection_type: str
    method: str
    parameters: dict[str, Any]
    active: bool = False
    detections: list[Detection] = field(default_factory=list, init=False, repr=False)
