"""Validate dashboard range rules without HTTP, a database or dependency overrides."""

from datetime import UTC, datetime, timedelta

import pytest
from app.features.dashboard.summary.request import DashboardSummaryRequest
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("start_time", "end_time", "expected_duration"),
    [
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00.000001Z", timedelta(microseconds=1)),
        # The end's local clock is earlier, but its UTC instant is later.
        ("2026-01-01T03:00:00+02:00", "2026-01-01T02:00:00Z", timedelta(hours=1)),
    ],
)
def test_accepts_positive_ranges_by_instant(start_time: str, end_time: str, expected_duration: timedelta) -> None:
    request = DashboardSummaryRequest.model_validate({"start_time": start_time, "end_time": end_time})

    assert request.end_time - request.start_time == expected_duration


@pytest.mark.parametrize(
    "end_time",
    [
        "2026-01-01T00:00:00Z",  # Equal bounds.
        "2025-12-31T23:59:59.999999Z",  # Earlier by a microsecond.
        "2026-01-01T01:00:00+01:00",  # Equal instant with a different offset.
        "2026-01-01T01:00:00+02:00",  # Later local clock, earlier instant.
    ],
)
def test_rejects_nonpositive_ranges_by_instant(end_time: str) -> None:
    with pytest.raises(ValidationError) as error:
        DashboardSummaryRequest.model_validate({"start_time": "2026-01-01T00:00:00Z", "end_time": end_time})

    assert [(item["loc"], item["type"]) for item in error.value.errors()] == [(("end_time",), "value_error")]
    assert "end_time must be after start_time" in error.value.errors()[0]["msg"]


@pytest.mark.parametrize("start_time", ["invalid", "2026-01-01T00:00:00"])
def test_invalid_start_reports_its_own_error_without_comparing_unvalidated_data(start_time: str) -> None:
    with pytest.raises(ValidationError) as error:
        DashboardSummaryRequest.model_validate({"start_time": start_time, "end_time": datetime(2026, 1, 2, tzinfo=UTC)})

    assert [item["loc"] for item in error.value.errors()] == [("start_time",)]
