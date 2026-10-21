from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    flow_count: int = Field(ge=0)
    detection_count: int = Field(ge=0)
    alert_count: int = Field(ge=0)
