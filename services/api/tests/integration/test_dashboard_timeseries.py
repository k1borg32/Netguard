"""Essential time-series behavior through real HTTP, JWT and TimescaleDB."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/dashboard/timeseries"
START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(hours=3)
PARAMS = {"start_time": START.isoformat(), "end_time": END.isoformat(), "interval": "1h"}
MICROSECOND = timedelta(microseconds=1)


@pytest.fixture
def headers(client: TestClient, create_user) -> dict[str, str]:
    create_user()
    response = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def insert_flow(db: psycopg.Connection, timestamp: datetime) -> None:
    db.execute(
        "INSERT INTO network_flows (flow_id, ts_start, ingested_at) VALUES (%s, %s, %s)",
        (uuid4(), timestamp, START - timedelta(days=1)),
    )


def insert_detection(db: psycopg.Connection, timestamp: datetime, severity: str = "HIGH") -> None:
    db.execute(
        "INSERT INTO detections (detection_id, created_at, first_ingested_at, type, method, severity) "
        "VALUES (%s, %s, %s, 'port_scan', 'threshold', %s)",
        (uuid4(), timestamp, START - timedelta(days=1), severity),
    )


def point(timestamp: datetime, flows: int = 0, detections: int = 0, by_severity: dict[str, int] | None = None) -> dict:
    if by_severity is None:
        by_severity = {"LOW": 0, "MEDIUM": 0, "HIGH": detections, "CRITICAL": 0}
    return {
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "flows_count": flows,
        "detections_count": detections,
        "detections_by_severity": by_severity,
    }


def test_empty_range_returns_zero_counts(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(URL, params=PARAMS, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-01-01T03:00:00Z",
        "interval": "1h",
        "data": [point(START + timedelta(hours=hour)) for hour in range(3)],
    }


@pytest.mark.parametrize(
    ("interval", "step"),
    [
        ("5m", timedelta(minutes=5)),
        ("15m", timedelta(minutes=15)),
        ("1h", timedelta(hours=1)),
        ("1d", timedelta(days=1)),
        ("10s", timedelta(seconds=10)),
        ("30s", timedelta(seconds=30)),
        ("1m", timedelta(minutes=1)),
    ],
)
def test_aggregates_both_datasets_with_gaps_and_chronological_order(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str], interval: str, step: timedelta
) -> None:
    # Out-of-order inserts and unequal counts detect sorting and join-multiplication bugs.
    insert_flow(db, START + step * 2)
    insert_flow(db, START)
    insert_flow(db, START + MICROSECOND)
    insert_detection(db, START + step * 2)
    for offset in range(3):
        insert_detection(db, START + MICROSECOND * offset)

    response = client.get(
        URL,
        params={"start_time": START.isoformat(), "end_time": (START + step * 3).isoformat(), "interval": interval},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["interval"] == interval
    assert response.json()["data"] == [point(START, 2, 3), point(START + step), point(START + step * 2, 1, 1)]


def test_aggregates_all_severities_in_sql_and_zero_fills_empty_buckets(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    for severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        insert_detection(db, START + timedelta(seconds=1), severity)
    insert_detection(db, START + timedelta(seconds=2), "HIGH")

    response = client.get(
        URL,
        params={
            "start_time": START.isoformat(),
            "end_time": (START + timedelta(seconds=30)).isoformat(),
            "interval": "10s",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data == [
        point(START, detections=5, by_severity={"LOW": 1, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 1}),
        point(START + timedelta(seconds=10)),
        point(START + timedelta(seconds=20)),
    ]
    assert sum(data[0]["detections_by_severity"].values()) == data[0]["detections_count"]


def test_partial_buckets_respect_half_open_range_and_bucket_boundaries(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    start = START + timedelta(minutes=17)
    end = START + timedelta(hours=2, minutes=8)
    for timestamp in [
        start - MICROSECOND,
        start,
        START + timedelta(hours=1) - MICROSECOND,
        START + timedelta(hours=1),
        end - MICROSECOND,
        end,
    ]:
        insert_flow(db, timestamp)
        insert_detection(db, timestamp)

    response = client.get(
        URL, params={**PARAMS, "start_time": start.isoformat(), "end_time": end.isoformat()}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["start_time"] == "2026-01-01T00:17:00Z"
    assert response.json()["end_time"] == "2026-01-01T02:08:00Z"
    assert response.json()["data"] == [
        point(START, 2, 2),
        point(START + timedelta(hours=1), 1, 1),
        point(START + timedelta(hours=2), 1, 1),
    ]


def test_small_interval_buckets_are_utc_aligned_for_offset_ranges(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    start = START + timedelta(seconds=5)
    end = START + timedelta(seconds=25)
    insert_flow(db, START + timedelta(seconds=6))
    insert_detection(db, START + timedelta(seconds=7), "CRITICAL")

    response = client.get(
        URL,
        params={
            "start_time": start.astimezone(timezone(timedelta(hours=2))).isoformat(),
            "end_time": end.astimezone(timezone(timedelta(hours=2))).isoformat(),
            "interval": "10s",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["start_time"] == "2026-01-01T00:00:05Z"
    assert response.json()["end_time"] == "2026-01-01T00:00:25Z"
    assert [bucket["timestamp"] for bucket in response.json()["data"]] == [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:10Z",
        "2026-01-01T00:00:20Z",
    ]
    assert response.json()["data"][0]["flows_count"] == 1
    assert response.json()["data"][0]["detections_by_severity"]["CRITICAL"] == 1


def test_defaults_are_last_24_hours(client: TestClient, headers: dict[str, str]) -> None:
    before = datetime.now(UTC)
    response = client.get(URL, headers=headers)
    after = datetime.now(UTC)

    assert response.status_code == 200, response.text
    body = response.json()
    start = datetime.fromisoformat(body["start_time"])
    end = datetime.fromisoformat(body["end_time"])
    assert before <= end <= after
    assert end - start == timedelta(days=1)
    assert body["interval"] == "1h"
    assert len(body["data"]) in {24, 25}
    assert all(item["flows_count"] == item["detections_count"] == 0 for item in body["data"])
    assert all(
        item["detections_by_severity"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0} for item in body["data"]
    )


@pytest.mark.parametrize(
    "params",
    [
        {**PARAMS, "start_time": END.isoformat()},
        {**PARAMS, "end_time": (START - MICROSECOND).isoformat()},
        {**PARAMS, "start_time": "bad-date"},
        {**PARAMS, "interval": "10m"},
        {**PARAMS, "end_time": (START + timedelta(days=367)).isoformat(), "interval": "1d"},
        {"interval": "10s"},
        {"from": START.isoformat(), "to": END.isoformat(), "interval": "1h"},
    ],
    ids=[
        "equal-bounds",
        "reversed-bounds",
        "invalid-timestamp",
        "unsupported-interval",
        "range-too-large",
        "too-many-buckets-for-default-range",
        "legacy-parameter-names",
    ],
)
def test_invalid_queries_return_422(client: TestClient, headers: dict[str, str], params: dict[str, str]) -> None:
    response = client.get(URL, params=params, headers=headers)

    assert response.status_code == 422, response.text
    assert response.json()["detail"]
    assert all(error["loc"][0] == "query" for error in response.json()["detail"])


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get(URL, params=PARAMS)

    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"


def test_openapi_documents_timeseries_contract(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][URL]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert set(parameters) == {"start_time", "end_time", "interval"}
    assert parameters["interval"]["schema"]["enum"] == ["10s", "30s", "1m", "5m", "15m", "1h", "1d"]
    assert set(schema["components"]["schemas"]["DashboardTimeseriesPoint"]["required"]) == {
        "timestamp",
        "flows_count",
        "detections_count",
        "detections_by_severity",
    }
    assert set(schema["components"]["schemas"]["DetectionsBySeverity"]["required"]) == {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }
