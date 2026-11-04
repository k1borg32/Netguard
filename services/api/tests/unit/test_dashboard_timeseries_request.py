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
    ("end", "interval"),
    [
        (START + timedelta(days=366), "1d"),
        (START + timedelta(minutes=5 * 2000), "5m"),
        (START + timedelta(seconds=10 * 2000), "10s"),
    ],
    ids=["maximum-range", "maximum-buckets-5m", "maximum-buckets-10s"],
)
def test_accepts_exact_query_limits(end: datetime, interval: str) -> None:
    request = DashboardTimeseriesRequest.model_validate({"start_time": START, "end_time": end, "interval": interval})

    assert request.start_time == START
    assert request.end_time == end


@pytest.mark.parametrize(
    ("interval", "step"), [("10s", timedelta(seconds=10)), ("5m", timedelta(minutes=5))], ids=["10s", "5m"]
)
def test_bucket_limit_includes_partial_buckets(interval: str, step: timedelta) -> None:
    # Shorter than 2000 intervals, but intersects 2001 aligned buckets.
    with pytest.raises(ValidationError, match="must not exceed 2000 buckets"):
        DashboardTimeseriesRequest.model_validate(
            {
                "start_time": START + timedelta(seconds=1),
                "end_time": START + step * 2000 + timedelta(microseconds=1),
                "interval": interval,
            }
        )


def test_rejects_timestamp_without_timezone() -> None:
    with pytest.raises(ValidationError):
        DashboardTimeseriesRequest.model_validate(
            {"start_time": "2026-01-01T00:00:00", "end_time": START + timedelta(hours=1)}
        )


@pytest.mark.parametrize("interval", ["10s", "30s", "1m", "5m", "15m", "1h", "1d"])
def test_accepts_supported_intervals(interval: str) -> None:
    DashboardTimeseriesRequest.model_validate(
        {"start_time": START, "end_time": START + timedelta(minutes=1), "interval": interval}
    )


@pytest.mark.parametrize(
    "values",
    [
        {"from": START, "to": START + timedelta(hours=1)},
        {"start_time": START, "end_time": START},
        {"start_time": START + timedelta(hours=1), "end_time": START},
        {"start_time": "not-a-timestamp", "end_time": START + timedelta(hours=1)},
    ],
    ids=["legacy-parameter-names", "equal-range", "reversed-range", "malformed-timestamp"],
)
def test_rejects_invalid_time_ranges(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DashboardTimeseriesRequest.model_validate(values)
