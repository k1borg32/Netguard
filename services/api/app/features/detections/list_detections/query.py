from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ListDetectionsQuery:
    start_time: datetime | None
    end_time: datetime | None
    severity: str | None
    detection_type: str | None
    method: str | None
    src_ip: str | None
    dst_ip: str | None
    protocol: str | None
    sort_order: str
    page: int
    page_size: int
