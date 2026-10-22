"""Flow filter validation without HTTP or infrastructure."""

from datetime import timedelta

import pytest
from app.features.flows.list_flows.request import ListFlowsRequest
from pydantic import ValidationError


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start_time": "2026-01-01T00:00:00Z"},
        {"end_time": "2026-01-01T00:00:00Z"},
        {"src_port": 0, "dst_port": 65535, "src_ip": "::1", "dst_ip": "192.0.2.1"},
        {"page": 2, "page_size": 100, "sort_order": "asc"},
    ],
)
def test_accepts_optional_filters_and_boundary_values(params: dict) -> None:
    ListFlowsRequest.model_validate(params)


def test_compares_range_by_instant() -> None:
    request = ListFlowsRequest.model_validate(
        {"start_time": "2026-01-01T03:00:00+02:00", "end_time": "2026-01-01T02:00:00Z"}
    )

    assert request.end_time - request.start_time == timedelta(hours=1)


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"start_time": "invalid"}, "start_time"),
        ({"start_time": "2026-01-01T00:00:00"}, "start_time"),
        ({"end_time": "2026-01-01T00:00:00"}, "end_time"),
        ({"start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-01T01:00:00+01:00"}, "end_time"),
        ({"start_time": "2026-01-02T00:00:00Z", "end_time": "2026-01-01T00:00:00Z"}, "end_time"),
        ({"src_ip": "not-an-ip"}, "src_ip"),
        ({"dst_ip": "192.0.2.0/24"}, "dst_ip"),
        ({"src_port": -1}, "src_port"),
        ({"dst_port": 65536}, "dst_port"),
        ({"protocol": ""}, "protocol"),
        ({"sort_order": "invalid"}, "sort_order"),
        ({"page": 0}, "page"),
        ({"page_size": 0}, "page_size"),
        ({"page_size": 101}, "page_size"),
    ],
)
def test_rejects_invalid_filters(params: dict, field: str) -> None:
    with pytest.raises(ValidationError) as error:
        ListFlowsRequest.model_validate(params)

    assert [item["loc"] for item in error.value.errors()] == [(field,)]
