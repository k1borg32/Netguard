"""Normalized network traffic identified by UUID and start time."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(eq=False, kw_only=True)
class NetworkFlow:
    flow_id: UUID
    ts_start: datetime
    trace_id: str | None = None
    ingested_at: datetime | None = None
    duration_ms: float | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str | None = None
    packets: int | None = None
    bytes: int | None = None
    tcp_flags: str | None = None
    source: str | None = None
    label: str | None = None
