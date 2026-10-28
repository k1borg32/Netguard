from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class GetFlowQuery:
    flow_id: UUID
    ts_start: datetime
