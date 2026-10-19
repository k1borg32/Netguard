"""Dashboard counts through real HTTP, JWT and TimescaleDB, without overrides."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from app.domain.user_role import UserRole
from fastapi.testclient import TestClient

URL = "/api/v1/dashboard/summary"
START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=1)
PARAMS = {"start_time": START.isoformat(), "end_time": END.isoformat()}
MICROSECOND = timedelta(microseconds=1)


@pytest.fixture
def tokens(client: TestClient, create_user) -> dict[str, str]:
    create_user()
    response = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def headers(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def insert_detection(db: psycopg.Connection, created_at: datetime):
    detection_id = uuid4()
    db.execute(
        "INSERT INTO detections (detection_id, created_at, type, method, severity, first_ingested_at) "
        "VALUES (%s, %s, 'port_scan', 'threshold', 'HIGH', %s)",
        (detection_id, created_at, START),
    )
    return detection_id


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_empty_summary_is_accessible_to_both_roles(client: TestClient, create_user, role: UserRole) -> None:
    create_user(role=role)
    login = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
    assert login.status_code == 200, login.text

    response = client.get(URL, params=PARAMS, headers={"Authorization": f"Bearer {login.json()['access_token']}"})

    assert response.status_code == 200, response.text
    assert response.json() == {"flow_count": 0, "detection_count": 0, "alert_count": 0}


def test_counts_use_independent_timestamps_and_half_open_boundaries(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    timestamps = [START - MICROSECOND, START, START + timedelta(hours=1), END - MICROSECOND, END, END + MICROSECOND]
    # The flow's composite key permits the same UUID at different start times.
    flow_id = uuid4()
    for timestamp in timestamps:
        db.execute(
            "INSERT INTO network_flows (flow_id, ts_start, ingested_at) VALUES (%s, %s, %s)",
            (flow_id, timestamp, START),
        )
        insert_detection(db, timestamp)
    insert_detection(db, START + timedelta(hours=2))  # A detection without an alert still counts.

    for timestamp, status in [
        (START - MICROSECOND, "NEW"),
        (START, "NEW"),
        (END - MICROSECOND, "ACKNOWLEDGED"),
        (END, "NEW"),
        (END + MICROSECOND, "NEW"),
    ]:
        # Alerts are counted by their own creation, even when the detection predates the range.
        detection_id = insert_detection(db, START - timedelta(days=1))
        db.execute(
            "INSERT INTO alerts (alert_id, detection_id, created_at, status, acknowledged_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (uuid4(), detection_id, timestamp, status, END if status == "ACKNOWLEDGED" else None),
        )

    response = client.get(URL, params=PARAMS, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"flow_count": 3, "detection_count": 4, "alert_count": 2}
    # Requests are read-only.
    assert db.execute("SELECT count(*) FROM network_flows").fetchone() == (6,)
    assert db.execute("SELECT count(*) FROM detections").fetchone() == (12,)
    assert db.execute("SELECT count(*) FROM alerts").fetchone() == (5,)


def test_flows_count_when_other_tables_are_empty(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    db.execute("INSERT INTO network_flows (flow_id, ts_start) VALUES (%s, %s)", (uuid4(), START))

    response = client.get(URL, params=PARAMS, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"flow_count": 1, "detection_count": 0, "alert_count": 0}


def test_equivalent_offsets_select_the_same_range(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    insert_detection(db, START)
    insert_detection(db, END)

    response = client.get(
        URL,
        params={"start_time": "2026-01-01T01:00:00+01:00", "end_time": "2026-01-02T02:00:00+02:00"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"flow_count": 0, "detection_count": 1, "alert_count": 0}


def test_adjacent_ranges_count_boundary_records_once(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    db.execute("INSERT INTO network_flows (flow_id, ts_start) VALUES (%s, %s)", (uuid4(), END))
    detection_id = insert_detection(db, END)
    db.execute(
        "INSERT INTO alerts (alert_id, detection_id, created_at) VALUES (%s, %s, %s)",
        (uuid4(), detection_id, END),
    )

    previous = client.get(URL, params=PARAMS, headers=headers)
    following = client.get(
        URL,
        params={"start_time": END.isoformat(), "end_time": (END + timedelta(days=1)).isoformat()},
        headers=headers,
    )

    assert previous.status_code == 200, previous.text
    assert following.status_code == 200, following.text
    assert previous.json() == {"flow_count": 0, "detection_count": 0, "alert_count": 0}
    assert following.json() == {"flow_count": 1, "detection_count": 1, "alert_count": 1}


def test_json_body_does_not_replace_required_query_parameters(client: TestClient, headers: dict[str, str]) -> None:
    response = client.request("GET", URL, json=PARAMS, headers=headers)

    assert response.status_code == 422, response.text
    assert {tuple(error["loc"]) for error in response.json()["detail"]} == {
        ("query", "start_time"),
        ("query", "end_time"),
    }


@pytest.mark.parametrize(
    ("params", "invalid_field"),
    [
        ({}, "start_time"),
        ({"end_time": END.isoformat()}, "start_time"),
        ({"start_time": START.isoformat()}, "end_time"),
        ({**PARAMS, "start_time": "invalid"}, "start_time"),
        ({**PARAMS, "end_time": "invalid"}, "end_time"),
        ({**PARAMS, "start_time": "2026-01-01T00:00:00"}, "start_time"),
        ({**PARAMS, "end_time": "2026-01-02T00:00:00"}, "end_time"),
        ({**PARAMS, "end_time": START.isoformat()}, "end_time"),
        ({"start_time": END.isoformat(), "end_time": START.isoformat()}, "end_time"),
        ({**PARAMS, "end_time": "2026-01-01T01:00:00+01:00"}, "end_time"),
    ],
)
def test_invalid_range_returns_422(
    client: TestClient, headers: dict[str, str], params: dict[str, str], invalid_field: str
) -> None:
    response = client.get(URL, params=params, headers=headers)

    assert response.status_code == 422, response.text
    assert any(error["loc"] == ["query", invalid_field] for error in response.json()["detail"])


@pytest.mark.parametrize("token_kind", ["missing", "malformed", "refresh", "deleted_user"])
def test_summary_rejects_unauthenticated_requests(
    client: TestClient, db: psycopg.Connection, tokens: dict[str, str], token_kind: str
) -> None:
    request_headers = {}
    if token_kind == "malformed":
        request_headers = {"Authorization": "Bearer invalid-token"}
    elif token_kind == "refresh":
        request_headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    elif token_kind == "deleted_user":
        db.execute("DELETE FROM users")
        request_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client.get(URL, params=PARAMS, headers=request_headers)

    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"


def test_openapi_documents_query_parameters_and_bearer_auth(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"][URL]["get"]
    assert "requestBody" not in operation
    assert {parameter["name"] for parameter in operation["parameters"]} == {"start_time", "end_time"}
    assert all(parameter["required"] and parameter["in"] == "query" for parameter in operation["parameters"])
    assert all(parameter["schema"]["format"] == "date-time" for parameter in operation["parameters"])
    assert operation["security"] == [{"HTTPBearer": []}]
    assert set(schema["components"]["schemas"]["DashboardSummaryResponse"]["required"]) == {
        "flow_count",
        "detection_count",
        "alert_count",
    }
