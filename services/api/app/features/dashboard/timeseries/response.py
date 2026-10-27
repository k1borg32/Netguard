from datetime import datetime

from pydantic import BaseModel, Field


class DashboardDetectionsBySeverity(BaseModel):
    LOW: int = Field(ge=0)
    MEDIUM: int = Field(ge=0)
    HIGH: int = Field(ge=0)
    CRITICAL: int = Field(ge=0)


class DashboardTimeseriesPoint(BaseModel):
    ts: datetime
    flows: int = Field(ge=0)
    packets: int = Field(ge=0)
    bytes: int = Field(ge=0)
    detections: DashboardDetectionsBySeverity


class DashboardTimeseriesResponse(BaseModel):
    interval_s: int
    points: list[DashboardTimeseriesPoint]
