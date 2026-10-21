from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetDetectionQuery:
    detection_id: UUID
