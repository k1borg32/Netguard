"""Essential request defaults, timezone rules and query limits without infrastructure."""

from datetime import UTC, datetime, timedelta

import pytest
from app.features.dashboard.timeseries.request import DashboardTimeseriesRequest
from pydantic import ValidationError

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_missing_start_is_relative_to_explicit_end_normalized_to_utc() -> None:
    request = DashboardTimeseriesRequest.model_validate({"end_time": "2026-01-02T02:00:00+02:00"})

    assert request.start_time == START
    assert request.end_time == START + timedelta(days=1)
    assert request.start_time.tzinfo is request.end_time.tzinfo is UTC


@pytest.mark.parametrize(
    ("end", "interval_s"),
    [(START + timedelta(days=366), 86400), (START + timedelta(minutes=5 * 500), 300)],
    ids=["maximum-range", "maximum-buckets"],
)
def test_accepts_exact_query_limits(end: datetime, interval_s: int) -> None:
    request = DashboardTimeseriesRequest.model_validate(
        {"start_time": START, "end_time": end, "interval_s": interval_s}
    )

    assert request.start_time == START
    assert request.end_time == end


def test_bucket_limit_includes_partial_buckets() -> None:
    # Shorter than 500 intervals, but intersects 501 aligned buckets.
    with pytest.raises(ValidationError, match="must not exceed 500 buckets"):
        DashboardTimeseriesRequest.model_validate(
            {
                "start_time": START + timedelta(minutes=1),
                "end_time": START + timedelta(minutes=5 * 500, microseconds=1),
                "interval_s": 300,
            }
        )


def test_rejects_timestamp_without_timezone() -> None:
    with pytest.raises(ValidationError):
        DashboardTimeseriesRequest.model_validate(
            {"start_time": "2026-01-01T00:00:00", "end_time": START + timedelta(hours=1)}
        )
