from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DetectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detection_id: UUID
    created_at: datetime
    first_ingested_at: datetime | None
    last_ingested_at: datetime | None
    type: str
    method: str
    severity: str
    confidence: float | None
    src_ip: str | None
    dst_ip: str | None
    window_size_s: int | None
    features: dict[str, Any] | None
    explanation: str | None


class ListDetectionsResponse(BaseModel):
    items: list[DetectionResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=500)
