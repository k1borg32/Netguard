from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetDetectionFlowsQuery:
    detection_id: UUID
    page: int
    page_size: int
    sort_order: str
