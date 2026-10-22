from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ListFlowsQuery:
    start_time: datetime | None
    end_time: datetime | None
    src_ip: str | None
    dst_ip: str | None
    src_port: int | None
    dst_port: int | None
    protocol: str | None
    sort_order: str
    page: int
    page_size: int
