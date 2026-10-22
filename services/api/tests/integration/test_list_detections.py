"""Detection filters and stable pages through real HTTP and TimescaleDB."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/detections"
START = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def seed_detection(db):
    def seed(**overrides):
        values = {
            "detection_id": uuid4(),
            "created_at": START,
            "type": "port_scan",
            "method": "rule",
            "severity": "HIGH",
            "src_ip": "192.0.2.1",
            "dst_ip": "2001:db8::1",
            "protocol": "TCP",
            **overrides,
        }
        db.execute(
            "INSERT INTO detections (detection_id, created_at, type, method, severity, src_ip, dst_ip, protocol) "
            "VALUES (%(detection_id)s, %(created_at)s, %(type)s, %(method)s, %(severity)s, "
            "%(src_ip)s, %(dst_ip)s, %(protocol)s)",
            values,
        )
        return str(values["detection_id"])

    return seed


@pytest.mark.parametrize(
    ("parameter", "column", "value"),
    [
        ("severity", "severity", "LOW"),
        ("detection_type", "type", "dns_tunnel"),
        ("method", "method", "statistical"),
        ("src_ip", "src_ip", "2001:db8::2"),
        ("dst_ip", "dst_ip", "192.0.2.2"),
        ("protocol", "protocol", "UDP"),
    ],
)
def test_each_filter_selects_only_matching_records(client: TestClient, seed_detection, parameter, column, value):
    seed_detection()
    expected = seed_detection(**{column: value})

    response = client.get(URL, params={parameter: value})

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [row["detection_id"] for row in response.json()["items"]] == [expected]


def test_filters_use_and_and_total_survives_empty_page(client: TestClient, seed_detection):
    expected = seed_detection(severity="LOW", method="statistical")
    seed_detection(severity="LOW")
    seed_detection(method="statistical")
    filters = {"severity": "LOW", "method": "statistical", "page_size": 1}

    first = client.get(URL, params=filters).json()
    assert [row["detection_id"] for row in first["items"]] == [expected]
    assert first["total"] == 1
    assert client.get(URL, params={**filters, "page": 2}).json() == {
        "items": [],
        "total": 1,
        "page": 2,
        "page_size": 1,
    }
    assert client.get(URL, params={"detection_type": "unknown"}).json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 50,
    }


def test_time_bounds_are_inclusive_exclusive_and_compare_instants(client: TestClient, seed_detection):
    seed_detection(created_at=START - timedelta(microseconds=1))
    expected = seed_detection(created_at=START)
    seed_detection(created_at=START + timedelta(hours=1))

    response = client.get(
        URL,
        params={
            "start_time": "2026-01-01T01:00:00+01:00",
            "end_time": "2026-01-01T01:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [row["detection_id"] for row in response.json()["items"]] == [expected]


@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_pages_have_stable_timestamp_ties_without_duplicates(client: TestClient, seed_detection, sort_order):
    for index in (4, 1, 5, 3, 2):
        seed_detection(detection_id=UUID(int=index))
    identifiers = []
    for page in (1, 2, 3):
        response = client.get(URL, params={"sort_order": sort_order, "page": page, "page_size": 2})
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["total"], body["page"], body["page_size"]) == (5, page, 2)
        identifiers.extend(row["detection_id"] for row in body["items"])
    expected = [str(UUID(int=index)) for index in range(1, 6)]
    assert identifiers == (expected if sort_order == "asc" else expected[::-1])


def test_legacy_limit_agrees_with_page_size(client: TestClient, seed_detection):
    seed_detection()
    response = client.get(URL, params={"limit": 1, "page_size": 1})
    assert response.status_code == 200, response.text
    assert response.json()["page_size"] == 1
    assert len(response.json()["items"]) == 1


@pytest.mark.parametrize(
    "parameters",
    [
        {"page": 0},
        {"page": "invalid"},
        {"page_size": 0},
        {"page_size": 501},
        {"limit": 1, "page_size": 2},
        {"sort_order": "sideways"},
        {"severity": "high"},
        {"src_ip": "invalid"},
        {"dst_ip": "300.1.1.1"},
        {"detection_type": ""},
        {"method": ""},
        {"protocol": ""},
        {"start_time": "2026-01-01T00:00:00"},
        {"start_time": "invalid", "end_time": "2026-01-01T01:00:00Z"},
        {"start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-01T00:00:00Z"},
        {"start_time": "2026-01-02T00:00:00Z", "end_time": "2026-01-01T00:00:00Z"},
    ],
)
def test_invalid_filter_or_pagination_returns_422(client: TestClient, parameters):
    assert client.get(URL, params=parameters).status_code == 422
