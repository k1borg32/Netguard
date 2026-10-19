from pydantic import BaseModel, Field

from app.features.alerts.common.response import AlertResponse


class ListAlertsResponse(BaseModel):
    items: list[AlertResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
