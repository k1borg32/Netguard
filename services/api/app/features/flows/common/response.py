from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FlowResponse(BaseModel):
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
