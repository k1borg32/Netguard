from datetime import datetime

from pydantic import BaseModel, Field

from .query import TimeseriesInterval


class DashboardTimeseriesPoint(BaseModel):
    timestamp: datetime
    flows_count: int = Field(ge=0)
    detections_count: int = Field(ge=0)


class DashboardTimeseriesResponse(BaseModel):
    start_time: datetime = Field(serialization_alias="from")
    end_time: datetime = Field(serialization_alias="to")
    interval: TimeseriesInterval
    data: list[DashboardTimeseriesPoint]
