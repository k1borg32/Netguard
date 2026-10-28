"""Essential request defaults, timezone rules and query limits without infrastructure."""

from datetime import UTC, datetime, timedelta

import pytest
from app.features.dashboard.timeseries.request import DashboardTimeseriesRequest
from pydantic import ValidationError

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_missing_start_is_relative_to_explicit_end_normalized_to_utc() -> None:
    request = DashboardTimeseriesRequest.model_validate({"to": "2026-01-02T02:00:00+02:00"})

    assert request.start_time == START
    assert request.end_time == START + timedelta(days=1)
    assert request.start_time.tzinfo is request.end_time.tzinfo is UTC


@pytest.mark.parametrize(
    ("end", "interval"),
    [(START + timedelta(days=366), "1d"), (START + timedelta(minutes=5 * 2000), "5m")],
    ids=["maximum-range", "maximum-buckets"],
)
def test_accepts_exact_query_limits(end: datetime, interval: str) -> None:
    request = DashboardTimeseriesRequest.model_validate({"from": START, "to": end, "interval": interval})

    assert request.start_time == START
    assert request.end_time == end


def test_bucket_limit_includes_partial_buckets() -> None:
    # Shorter than 2000 intervals, but intersects 2001 aligned buckets.
    with pytest.raises(ValidationError, match="must not exceed 2000 buckets"):
        DashboardTimeseriesRequest.model_validate(
            {
                "from": START + timedelta(minutes=1),
                "to": START + timedelta(minutes=5 * 2000, microseconds=1),
                "interval": "5m",
            }
        )


def test_rejects_timestamp_without_timezone() -> None:
    with pytest.raises(ValidationError):
        DashboardTimeseriesRequest.model_validate({"from": "2026-01-01T00:00:00", "to": START + timedelta(hours=1)})
