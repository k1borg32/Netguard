from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GetDashboardTimeseriesQuery:
    start_time: datetime
    end_time: datetime
    interval_s: int
