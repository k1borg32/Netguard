from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AcknowledgeAlertCommand:
    alert_id: UUID
