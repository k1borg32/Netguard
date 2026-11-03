from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DetectionFlowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    flow_id: UUID
    ts_start: datetime
    trace_id: str | None
    ingested_at: datetime | None
    duration_ms: float | None
    src_ip: str | None
    dst_ip: str | None
    src_port: int | None
    dst_port: int | None
    protocol: str | None
    packets: int | None
    bytes: int | None
    tcp_flags: str | None
    source: str | None
    label: str | None


class GetDetectionFlowsResponse(BaseModel):
    items: list[DetectionFlowResponse]
    total: int = Field(ge=0, description="Number of stored flows matching the detection's trace IDs.")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=500)
