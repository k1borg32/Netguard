from datetime import datetime

from pydantic import BaseModel, Field

from .query import TimeseriesInterval


class DetectionsBySeverity(BaseModel):
    LOW: int = Field(ge=0)
    MEDIUM: int = Field(ge=0)
    HIGH: int = Field(ge=0)
    CRITICAL: int = Field(ge=0)


class DashboardTimeseriesPoint(BaseModel):
    timestamp: datetime
    flows_count: int = Field(ge=0)
    detections_count: int = Field(ge=0)
    detections_by_severity: DetectionsBySeverity


class DashboardTimeseriesResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    interval: TimeseriesInterval
    data: list[DashboardTimeseriesPoint]
