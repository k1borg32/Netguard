from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: UUID
    detection_id: UUID
    status: str
    created_at: datetime
    acknowledged_at: datetime | None
