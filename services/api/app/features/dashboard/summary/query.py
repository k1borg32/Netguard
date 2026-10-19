from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GetDashboardSummaryQuery:
    start_time: datetime
    end_time: datetime
