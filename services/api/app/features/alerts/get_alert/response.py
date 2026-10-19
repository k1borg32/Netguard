from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.features.alerts.common.response import AlertResponse


class AlertDetectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detection_id: UUID
    configuration_id: UUID | None
    created_at: datetime
    first_ingested_at: datetime | None
    type: str
    method: str
    severity: str
    confidence: float | None
    src_ip: str | None
    dst_ip: str | None
    src_port: int | None
    dst_port: int | None
    protocol: str | None
    window_size_s: int | None
    window_start: datetime | None
    window_end: datetime | None
    explanation: str | None
    features: dict[str, Any] | None
    trace_ids: list[str]


class GetAlertResponse(AlertResponse):
    detection: AlertDetectionResponse
