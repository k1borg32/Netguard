"""Essential time-series behavior through real HTTP, JWT and TimescaleDB."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/dashboard/timeseries"
START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(hours=3)
PARAMS = {"start_time": START.isoformat(), "end_time": END.isoformat(), "interval_s": 3600}
MICROSECOND = timedelta(microseconds=1)


@pytest.fixture
def headers(client: TestClient, create_user) -> dict[str, str]:
    create_user()
    response = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def insert_flow(db: psycopg.Connection, timestamp: datetime, packets: int | None = 2, size: int | None = 100) -> None:
    db.execute(
        "INSERT INTO network_flows (flow_id, ts_start, ingested_at, packets, bytes) VALUES (%s, %s, %s, %s, %s)",
        (uuid4(), timestamp, START - timedelta(days=1), packets, size),
    )


def insert_detection(db: psycopg.Connection, timestamp: datetime, severity: str = "HIGH") -> None:
    db.execute(
        "INSERT INTO detections (detection_id, created_at, first_ingested_at, type, method, severity) "
        "VALUES (%s, %s, %s, 'port_scan', 'threshold', %s)",
        (uuid4(), timestamp, START - timedelta(days=1), severity),
    )


def point(timestamp: datetime, flows: int = 0, detections: int = 0) -> dict:
    return {
        "ts": timestamp.isoformat().replace("+00:00", "Z"),
        "flows": flows,
        "packets": flows * 2,
        "bytes": flows * 100,
        "detections": {"LOW": 0, "MEDIUM": 0, "HIGH": detections, "CRITICAL": 0},
    }


def test_empty_range_returns_zero_counts(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(URL, params=PARAMS, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "interval_s": 3600,
        "points": [point(START + timedelta(hours=hour)) for hour in range(3)],
    }


@pytest.mark.parametrize(
    ("interval_s", "step"),
    [
        (5, timedelta(seconds=5)),
        (15, timedelta(seconds=15)),
        (60, timedelta(minutes=1)),
        (300, timedelta(minutes=5)),
        (900, timedelta(minutes=15)),
        (3600, timedelta(hours=1)),
        (86400, timedelta(days=1)),
    ],
)
def test_aggregates_both_datasets_with_gaps_and_chronological_order(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str], interval_s: int, step: timedelta
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
        params={"start_time": START.isoformat(), "end_time": (START + step * 3).isoformat(), "interval_s": interval_s},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["interval_s"] == interval_s
    assert response.json()["points"] == [point(START, 2, 3), point(START + step), point(START + step * 2, 1, 1)]


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
    assert response.json()["points"] == [
        point(START, 2, 2),
        point(START + timedelta(hours=1), 1, 1),
        point(START + timedelta(hours=2), 1, 1),
    ]


def test_defaults_are_last_24_hours(client: TestClient, headers: dict[str, str]) -> None:
    before = datetime.now(UTC)
    response = client.get(URL, headers=headers)
    after = datetime.now(UTC)

    assert response.status_code == 200, response.text
    body = response.json()
    first = datetime.fromisoformat(body["points"][0]["ts"])
    last = datetime.fromisoformat(body["points"][-1]["ts"])
    assert before - timedelta(days=1, hours=1) < first <= after - timedelta(days=1)
    assert before - timedelta(hours=1) < last <= after
    assert body["interval_s"] == 3600
    assert len(body["points"]) in {24, 25}
    assert all(item == point(datetime.fromisoformat(item["ts"])) for item in body["points"])


@pytest.mark.parametrize(
    "params",
    [
        {**PARAMS, "start_time": END.isoformat()},
        {**PARAMS, "end_time": (START - MICROSECOND).isoformat()},
        {**PARAMS, "start_time": "bad-date"},
        {**PARAMS, "interval_s": 0},
        {**PARAMS, "interval_s": "1h"},
        {**PARAMS, "interval_s": 86401},
        {**PARAMS, "interval_s": 5},
        {**PARAMS, "end_time": (START + timedelta(days=367)).isoformat(), "interval_s": 86400},
    ],
    ids=[
        "equal-bounds",
        "reversed-bounds",
        "invalid-timestamp",
        "zero-interval",
        "text-interval",
        "interval-too-large",
        "too-many-points",
        "range-too-large",
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


def test_severity_counts_and_nullable_flow_totals(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    insert_flow(db, START, packets=None, size=None)
    insert_flow(db, START, packets=7, size=4096)
    for severity in ["LOW", "MEDIUM", "HIGH", "HIGH", "CRITICAL"]:
        insert_detection(db, START, severity)
    response = client.get(URL, params={**PARAMS, "end_time": (START + timedelta(hours=1)).isoformat()}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "interval_s": 3600,
        "points": [
            {
                "ts": "2026-01-01T00:00:00Z",
                "flows": 2,
                "packets": 7,
                "bytes": 4096,
                "detections": {"LOW": 1, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 1},
            }
        ],
    }


def test_custom_second_interval_uses_same_origin_for_all_aggregates(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    origin = datetime(1970, 1, 1, tzinfo=UTC)
    aligned = START - (START - origin) % timedelta(seconds=7)
    insert_flow(db, START)
    insert_detection(db, START)
    response = client.get(
        URL,
        params={
            "start_time": START.isoformat(),
            "end_time": (aligned + timedelta(seconds=14)).isoformat(),
            "interval_s": 7,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"interval_s": 7, "points": [point(aligned, 1, 1), point(aligned + timedelta(seconds=7))]}


def test_openapi_matches_dashboard_contract(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    parameters = schema["paths"][URL]["get"]["parameters"]
    assert {p["name"] for p in parameters} == {"start_time", "end_time", "interval_s"}
    assert set(schema["components"]["schemas"]["DashboardTimeseriesResponse"]["properties"]) == {"interval_s", "points"}
    assert set(schema["components"]["schemas"]["DashboardTimeseriesPoint"]["properties"]) == {
        "ts",
        "flows",
        "packets",
        "bytes",
        "detections",
    }
