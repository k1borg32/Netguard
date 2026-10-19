from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetAlertQuery:
    alert_id: UUID
