from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

TimeseriesInterval = Literal["10s", "30s", "1m", "5m", "15m", "1h", "1d"]
BUCKET_SIZES: dict[TimeseriesInterval, timedelta] = {
    "10s": timedelta(seconds=10),
    "30s": timedelta(seconds=30),
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


@dataclass(frozen=True)
class GetDashboardTimeseriesQuery:
    start_time: datetime
    end_time: datetime
    interval: TimeseriesInterval
