"""Alerts through real HTTP, authentication and disposable TimescaleDB."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
import pytest
from app.domain.user_role import UserRole
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

URL = "/api/alerts"
START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=1)


@pytest.fixture
def tokens(client: TestClient, create_user) -> dict[str, str]:
    create_user()
    response = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def headers(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def insert_alert(db: psycopg.Connection):
    def insert(
        *,
        created_at=START,
        status="NEW",
        severity="HIGH",
        detection_type="port_scan",
        src_ip="192.0.2.1",
        dst_ip="2001:db8::1",
        protocol="TCP",
        alert_id=None,
    ):
        alert_id = alert_id or uuid4()
        detection_id = uuid4()
        db.execute(
            "INSERT INTO detections (detection_id, created_at, type, method, severity, src_ip, dst_ip, protocol) "
            "VALUES (%s, %s, %s, 'threshold', %s, %s, %s, %s)",
            (detection_id, START - timedelta(days=2), detection_type, severity, src_ip, dst_ip, protocol),
        )
        db.execute(
            "INSERT INTO alerts (alert_id, detection_id, created_at, status, acknowledged_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (alert_id, detection_id, created_at, status, END if status == "ACKNOWLEDGED" else None),
        )
        return alert_id, detection_id

    return insert


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_both_roles_can_list_read_and_acknowledge(client, create_user, insert_alert, role) -> None:
    create_user(role=role)
    login = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    alert_id, _ = insert_alert()
    for method, path in [("GET", URL), ("GET", f"{URL}/{alert_id}"), ("PATCH", f"{URL}/{alert_id}/acknowledge")]:
        response = client.request(method, path, headers=headers)
        assert response.status_code == 200, response.text


def test_empty_list(client, headers) -> None:
    response = client.get(URL, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 50,
        "total_pages": 0,
        "has_next": False,
        "has_previous": False,
    }
    response = client.get(URL, params={"page": 2}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total_pages"] == 0
    assert response.json()["has_next"] is False
    assert response.json()["has_previous"] is False


@pytest.mark.parametrize("direction", ["asc", "desc"])
@pytest.mark.parametrize("page_size, total_pages", [(1, 5), (2, 3), (5, 1), (10, 1)])
def test_pagination_has_stable_ties_and_preserves_total(
    client, headers, insert_alert, direction, page_size, total_pages
) -> None:
    ids = [UUID(int=value) for value in range(1, 6)]
    for index, alert_id in enumerate(ids):
        insert_alert(alert_id=alert_id, created_at=START + timedelta(hours=index // 2))
    expected = ids if direction == "asc" else list(reversed(ids))
    collected = []
    for page in range(1, total_pages + 2):
        response = client.get(
            URL, params={"page": page, "page_size": page_size, "sort_order": direction}, headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["total"], body["page"], body["page_size"]) == (5, page, page_size)
        assert body["total_pages"] == total_pages
        assert body["has_next"] is (page < total_pages)
        assert body["has_previous"] is (page > 1)
        assert [UUID(item["alert_id"]) for item in body["items"]] == expected[(page - 1) * page_size : page * page_size]
        collected.extend(UUID(item["alert_id"]) for item in body["items"])
    assert collected == expected
    response = client.get(URL, headers=headers)
    assert [UUID(item["alert_id"]) for item in response.json()["items"]] == list(reversed(ids))


def test_page_count_uses_filtered_total(client, headers, insert_alert) -> None:
    for _ in range(3):
        insert_alert(severity="HIGH")
        insert_alert(severity="LOW")
    response = client.get(URL, params={"severity": "HIGH", "page": 2, "page_size": 2}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["total_pages"], body["page"]) == (3, 2, 2)
    assert len(body["items"]) == 1
    assert body["has_previous"] is True
    assert body["has_next"] is False


@pytest.mark.parametrize(
    "field, value, other",
    [
        ("status", "ACKNOWLEDGED", "NEW"),
        ("severity", "CRITICAL", "LOW"),
        ("detection_type", "dos", "port_scan"),
        ("src_ip", "192.0.2.5", "192.0.2.6"),
        ("dst_ip", "2001:db8::5", "2001:db8::6"),
        ("protocol", "UDP", "TCP"),
    ],
)
def test_each_filter_applies_to_items_and_total(client, headers, insert_alert, field, value, other) -> None:
    expected, _ = insert_alert(**{field: value})
    insert_alert(**{field: other})
    response = client.get(URL, params={field: value}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [item["alert_id"] for item in response.json()["items"]] == [str(expected)]


def test_combined_filters_use_and_and_normalize_ipv6(client, headers, insert_alert) -> None:
    expected, _ = insert_alert(severity="CRITICAL", status="ACKNOWLEDGED")
    insert_alert(severity="LOW", status="ACKNOWLEDGED")
    insert_alert(severity="CRITICAL", status="NEW")
    params = {"severity": "CRITICAL", "status": "ACKNOWLEDGED", "dst_ip": "2001:0db8:0:0:0:0:0:1"}
    response = client.get(URL, params=params, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["alert_id"] == str(expected)
    response = client.get(URL, params={**params, "protocol": "UDP"}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


@pytest.mark.parametrize("bounds", ["both", "start", "end"])
def test_time_filters_use_alert_time_and_half_open_boundaries(client, headers, insert_alert, bounds) -> None:
    timestamps = [START - timedelta(microseconds=1), START, END - timedelta(microseconds=1), END]
    ids = [str(insert_alert(created_at=timestamp)[0]) for timestamp in timestamps]
    params = {"sort_order": "asc"}
    if bounds in {"both", "start"}:
        params["start_time"] = "2026-01-01T01:00:00+01:00"
    if bounds in {"both", "end"}:
        params["end_time"] = "2026-01-02T02:00:00+02:00"
    expected = {"both": ids[1:3], "start": ids[1:], "end": ids[:3]}[bounds]
    response = client.get(URL, params=params, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == len(expected)
    assert [item["alert_id"] for item in response.json()["items"]] == expected


def test_detail_contains_full_detection_without_mutating_rows(client, db, headers, insert_alert) -> None:
    alert_id, detection_id = insert_alert()
    configuration_id = uuid4()
    db.execute(
        "INSERT INTO detection_configs VALUES (%s, 'port_scan', 'threshold', %s, false)",
        (configuration_id, Jsonb({"threshold": 10})),
    )
    db.execute(
        "UPDATE detections SET configuration_id = %s, confidence = 0.75, src_port = 1234, dst_port = 443, "
        "window_size_s = 60, window_start = %s, window_end = %s, explanation = 'Threshold exceeded', "
        "features = %s, trace_ids = %s, first_ingested_at = %s WHERE detection_id = %s",
        (configuration_id, START, END, Jsonb({"packets": 12}), ["trace-1", "trace-2"], START, detection_id),
    )
    before = db.execute("SELECT * FROM detections WHERE detection_id = %s", (detection_id,)).fetchone()
    response = client.get(f"{URL}/{alert_id}", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["alert_id"] == str(alert_id)
    assert body["status"] == "NEW"
    assert body["acknowledged_at"] is None
    assert body["detection"] == {
        "detection_id": str(detection_id),
        "configuration_id": str(configuration_id),
        "created_at": "2025-12-30T00:00:00Z",
        "first_ingested_at": "2026-01-01T00:00:00Z",
        "type": "port_scan",
        "method": "threshold",
        "severity": "HIGH",
        "confidence": 0.75,
        "src_ip": "192.0.2.1",
        "dst_ip": "2001:db8::1",
        "src_port": 1234,
        "dst_port": 443,
        "protocol": "TCP",
        "window_size_s": 60,
        "window_start": "2026-01-01T00:00:00Z",
        "window_end": "2026-01-02T00:00:00Z",
        "explanation": "Threshold exceeded",
        "features": {"packets": 12},
        "trace_ids": ["trace-1", "trace-2"],
    }
    assert db.execute("SELECT * FROM detections WHERE detection_id = %s", (detection_id,)).fetchone() == before
    assert db.execute("SELECT status, acknowledged_at FROM alerts WHERE alert_id = %s", (alert_id,)).fetchone() == (
        "NEW",
        None,
    )


def test_detail_supports_nullable_detection_fields(client, headers, insert_alert) -> None:
    alert_id, _ = insert_alert(src_ip=None, dst_ip=None, protocol=None)
    response = client.get(f"{URL}/{alert_id}", headers=headers)
    assert response.status_code == 200, response.text
    detection = response.json()["detection"]
    for field in ("src_ip", "dst_ip", "protocol", "features", "configuration_id", "confidence", "window_start"):
        assert detection[field] is None
    assert detection["trace_ids"] == []


def test_acknowledgement_commits_is_idempotent_and_only_changes_target(client, db, headers, insert_alert) -> None:
    alert_id, detection_id = insert_alert()
    other_id, _ = insert_alert()
    detection_before = db.execute("SELECT * FROM detections WHERE detection_id = %s", (detection_id,)).fetchone()
    before = db.execute("SELECT clock_timestamp()").fetchone()[0]
    first = client.patch(f"{URL}/{alert_id}/acknowledge", headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    timestamp = datetime.fromisoformat(body["acknowledged_at"])
    after = db.execute("SELECT clock_timestamp()").fetchone()[0]
    assert before <= timestamp <= after
    assert body["status"] == "ACKNOWLEDGED"
    second = client.patch(f"{URL}/{alert_id}/acknowledge", headers=headers)
    assert second.status_code == 200, second.text
    assert second.json() == body
    assert db.execute("SELECT status, acknowledged_at FROM alerts WHERE alert_id = %s", (alert_id,)).fetchone() == (
        "ACKNOWLEDGED",
        timestamp,
    )
    assert db.execute("SELECT status, acknowledged_at FROM alerts WHERE alert_id = %s", (other_id,)).fetchone() == (
        "NEW",
        None,
    )
    assert (
        db.execute("SELECT * FROM detections WHERE detection_id = %s", (detection_id,)).fetchone() == detection_before
    )
    detail = client.get(f"{URL}/{alert_id}", headers=headers)
    assert detail.json()["acknowledged_at"] == body["acknowledged_at"]
    listed = client.get(URL, params={"status": "ACKNOWLEDGED"}, headers=headers)
    assert listed.json()["items"] == [body]


def test_concurrent_acknowledgements_share_first_timestamp(client, db, headers, insert_alert) -> None:
    alert_id, _ = insert_alert()

    def acknowledge(_):
        return client.patch(f"{URL}/{alert_id}/acknowledge", headers=headers)

    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(acknowledge, range(4)))
    assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
    assert all(response.json() == responses[0].json() for response in responses)
    stored = db.execute("SELECT acknowledged_at FROM alerts WHERE alert_id = %s", (alert_id,)).fetchone()[0]
    assert stored == datetime.fromisoformat(responses[0].json()["acknowledged_at"])


@pytest.mark.parametrize("method, suffix", [("GET", ""), ("PATCH", "/acknowledge")])
def test_missing_alert_returns_404(client, headers, method, suffix) -> None:
    response = client.request(method, f"{URL}/{uuid4()}{suffix}", headers=headers)
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Alert not found"}


@pytest.mark.parametrize("method, suffix", [("GET", ""), ("PATCH", "/acknowledge")])
def test_invalid_alert_id_returns_422(client, headers, method, suffix) -> None:
    response = client.request(method, f"{URL}/invalid-uuid{suffix}", headers=headers)
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["path", "id"]


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": "invalid"},
        {"page_size": 0},
        {"page_size": 101},
        {"sort_order": "invalid"},
        {"severity": "high"},
        {"status": "CLOSED"},
        {"src_ip": "invalid"},
        {"dst_ip": "192.0.2.1/24"},
        {"detection_type": ""},
        {"protocol": ""},
        {"start_time": "invalid"},
        {"start_time": "2026-01-01T00:00:00"},
        {"end_time": "2026-01-01T00:00:00"},
        {"start_time": START.isoformat(), "end_time": START.isoformat()},
        {"start_time": END.isoformat(), "end_time": START.isoformat()},
    ],
)
def test_invalid_list_parameters_return_422(client, headers, params) -> None:
    response = client.get(URL, params=params, headers=headers)
    assert response.status_code == 422, response.text
    assert all(error["loc"][0] == "query" for error in response.json()["detail"])


@pytest.mark.parametrize("method, suffix", [("GET", ""), ("GET", "/{id}"), ("PATCH", "/{id}/acknowledge")])
@pytest.mark.parametrize("token_kind", ["missing", "malformed", "refresh", "deleted_user"])
def test_endpoints_reject_invalid_authentication(client, db, tokens, insert_alert, method, suffix, token_kind) -> None:
    alert_id, _ = insert_alert()
    request_headers = {}
    if token_kind == "malformed":
        request_headers = {"Authorization": "Bearer invalid-token"}
    elif token_kind == "refresh":
        request_headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    elif token_kind == "deleted_user":
        db.execute("DELETE FROM users")
        request_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = client.request(method, URL + suffix.format(id=alert_id), headers=request_headers)
    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"
    assert db.execute("SELECT status, acknowledged_at FROM alerts WHERE alert_id = %s", (alert_id,)).fetchone() == (
        "NEW",
        None,
    )


def test_openapi_documents_authentication_query_and_path_parameters(client) -> None:
    schema = client.get("/openapi.json").json()
    assert set(schema["components"]["schemas"]["ListAlertsResponse"]["required"]) == {
        "items",
        "total",
        "page",
        "page_size",
        "total_pages",
        "has_next",
        "has_previous",
    }
    for path, method in [(URL, "get"), (URL + "/{id}", "get"), (URL + "/{id}/acknowledge", "patch")]:
        operation = schema["paths"][path][method]
        assert "requestBody" not in operation
        assert operation["security"] == [{"HTTPBearer": []}]
        if path == URL:
            assert {p["name"] for p in operation["parameters"]} == {
                "start_time",
                "end_time",
                "status",
                "severity",
                "detection_type",
                "src_ip",
                "dst_ip",
                "protocol",
                "sort_order",
                "page",
                "page_size",
            }
            assert all(parameter["in"] == "query" for parameter in operation["parameters"])
        else:
            assert operation["parameters"] == [
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid", "title": "Id"},
                }
            ]
            assert "404" in operation["responses"]
