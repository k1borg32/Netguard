"""Alert list bounds are optional and compare timezone-aware instants."""

from datetime import timedelta

import pytest
from app.features.alerts.list_alerts.request import ListAlertsRequest
from pydantic import ValidationError


@pytest.mark.parametrize("values", [{}, {"start_time": "2026-01-01T00:00:00Z"}, {"end_time": "2026-01-01T00:00:00Z"}])
def test_each_time_bound_is_optional(values) -> None:
    ListAlertsRequest(**values)


def test_positive_range_compares_instants() -> None:
    request = ListAlertsRequest(start_time="2026-01-01T01:00:00+01:00", end_time="2026-01-01T00:00:00.000001Z")
    assert request.end_time - request.start_time == timedelta(microseconds=1)


@pytest.mark.parametrize("end_time", ["2026-01-01T01:00:00+01:00", "2025-12-31T23:59:59Z"])
def test_equal_or_reversed_range(end_time) -> None:
    with pytest.raises(ValidationError) as error:
        ListAlertsRequest(start_time="2026-01-01T00:00:00Z", end_time=end_time)
    assert error.value.errors()[0]["loc"] == ("end_time",)
