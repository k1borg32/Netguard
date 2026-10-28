"""Detection evidence pages through real HTTP and disposable TimescaleDB."""

import socket
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/detections"
START = datetime(2026, 1, 1, tzinfo=UTC)
NULLABLE_FLOW_FIELDS = {
    "ingested_at",
    "duration_ms",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "packets",
    "bytes",
    "tcp_flags",
    "source",
    "label",
}


@pytest.fixture
def seed_detection(db):
    def seed(trace_ids=()):
        detection_id = uuid4()
        db.execute(
            "INSERT INTO detections (detection_id, created_at, type, method, severity, trace_ids) "
            "VALUES (%s, %s, 'port_scan', 'rule', 'HIGH', %s)",
            (detection_id, START, list(trace_ids)),
        )
        return detection_id

    return seed


@pytest.fixture
def seed_flow(db):
    def seed(**overrides):
        values = {
            "flow_id": uuid4(),
            "ts_start": START,
            "trace_id": "trace-matched",
            "ingested_at": START + timedelta(microseconds=123456),
            "duration_ms": 12.5,
            "src_ip": "2001:db8::1",
            "dst_ip": "192.0.2.10",
            "src_port": 12345,
            "dst_port": 443,
            "protocol": "TCP",
            "packets": 5,
            "bytes": 1024,
            "tcp_flags": "S",
            "source": "simulator",
            "label": "port_scan",
            **overrides,
        }
        db.execute(
            "INSERT INTO network_flows (flow_id, ts_start, trace_id, ingested_at, duration_ms, src_ip, "
            "dst_ip, src_port, dst_port, protocol, packets, bytes, tcp_flags, source, label) "
            "VALUES (%(flow_id)s, %(ts_start)s, %(trace_id)s, %(ingested_at)s, %(duration_ms)s, %(src_ip)s, "
            "%(dst_ip)s, %(src_port)s, %(dst_port)s, %(protocol)s, %(packets)s, %(bytes)s, "
            "%(tcp_flags)s, %(source)s, %(label)s)",
            values,
        )
        return values

    return seed


def test_public_page_uses_only_requested_trace_sample_without_duplicates_or_writes(
    client: TestClient,
    db,
    seed_detection,
    seed_flow,
):
    matching = seed_flow()
    seed_flow(trace_id="trace-unrelated")
    seed_flow(trace_id=None)
    seed_detection(["trace-unrelated"])
    detection_id = seed_detection(["trace-matched", "trace-matched", "trace-missing"])
    before_flows = db.execute("SELECT * FROM network_flows ORDER BY ts_start, flow_id").fetchall()
    before_detections = db.execute("SELECT * FROM detections ORDER BY detection_id").fetchall()

    response = client.get(f"{URL}/{detection_id}/flows")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [
            {
                "flow_id": str(matching["flow_id"]),
                "ts_start": "2026-01-01T00:00:00Z",
                "trace_id": "trace-matched",
                "ingested_at": "2026-01-01T00:00:00.123456Z",
                "duration_ms": 12.5,
                "src_ip": "2001:db8::1",
                "dst_ip": "192.0.2.10",
                "src_port": 12345,
                "dst_port": 443,
                "protocol": "TCP",
                "packets": 5,
                "bytes": 1024,
                "tcp_flags": "S",
                "source": "simulator",
                "label": "port_scan",
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 50,
    }
    assert db.execute("SELECT * FROM network_flows ORDER BY ts_start, flow_id").fetchall() == before_flows
    assert db.execute("SELECT * FROM detections ORDER BY detection_id").fetchall() == before_detections


@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_stable_pages_keep_composite_flow_keys_and_total(client: TestClient, seed_detection, seed_flow, sort_order):
    detection_id = seed_detection(["trace-matched"])
    keys = [
        (UUID(int=1), START),
        (UUID(int=2), START),
        (UUID(int=1), START + timedelta(seconds=1)),
        (UUID(int=3), START + timedelta(seconds=1)),
        (UUID(int=4), START + timedelta(seconds=2)),
    ]
    for flow_id, timestamp in reversed(keys):
        seed_flow(flow_id=flow_id, ts_start=timestamp)
    expected = sorted(keys, key=lambda key: (key[1], key[0]), reverse=sort_order == "desc")
    collected = []
    for page in (1, 2, 3, 4):
        response = client.get(
            f"{URL}/{detection_id}/flows",
            params={
                "page": page,
                "page_size": 2,
                "sort_order": sort_order,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["total"], body["page"], body["page_size"]) == (5, page, 2)
        actual = [(UUID(row["flow_id"]), datetime.fromisoformat(row["ts_start"])) for row in body["items"]]
        assert actual == expected[(page - 1) * 2 : page * 2]
        collected.extend(actual)
    assert collected == expected
    default = client.get(f"{URL}/{detection_id}/flows").json()
    assert [(UUID(row["flow_id"]), datetime.fromisoformat(row["ts_start"])) for row in default["items"]] == sorted(
        keys,
        key=lambda key: (key[1], key[0]),
        reverse=True,
    )


@pytest.mark.parametrize("trace_ids", [[], ["trace-missing"]])
def test_existing_detection_without_retained_matches_returns_empty_page(
    client: TestClient,
    seed_detection,
    seed_flow,
    trace_ids,
):
    detection_id = seed_detection(trace_ids)
    seed_flow()

    response = client.get(f"{URL}/{detection_id}/flows", params={"page": 3})

    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0, "page": 3, "page_size": 50}


def test_unknown_detection_returns_404_instead_of_empty_page(client: TestClient, seed_detection, seed_flow):
    seed_detection(["trace-matched"])
    seed_flow()

    response = client.get(f"{URL}/{uuid4()}/flows")

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Detection not found"}


def test_flow_evidence_can_be_nullable(client: TestClient, seed_detection, seed_flow):
    detection_id = seed_detection(["trace-matched"])
    seed_flow(**dict.fromkeys(NULLABLE_FLOW_FIELDS))

    response = client.get(f"{URL}/{detection_id}/flows")

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert all(item[field] is None for field in NULLABLE_FLOW_FIELDS)
    assert item["trace_id"] == "trace-matched"


def test_page_size_upper_bound_is_accepted(client: TestClient, seed_detection, seed_flow):
    detection_id = seed_detection(["trace-matched"])
    seed_flow()

    response = client.get(f"{URL}/{detection_id}/flows", params={"page_size": 500})

    assert response.status_code == 200, response.text
    assert response.json()["page_size"] == 500
    assert len(response.json()["items"]) == 1


@pytest.mark.parametrize("identifier", ["not-a-uuid", "123", "550e8400-e29b-41d4-a716-44665544000g"])
def test_invalid_uuid_returns_422(client: TestClient, identifier):
    response = client.get(f"{URL}/{identifier}/flows")

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["path", "id"]


@pytest.mark.parametrize(
    "parameters",
    [
        {"page": 0},
        {"page": -1},
        {"page": "invalid"},
        {"page_size": 0},
        {"page_size": -1},
        {"page_size": 501},
        {"page_size": "invalid"},
        {"sort_order": "sideways"},
    ],
)
def test_invalid_pagination_or_sort_returns_422(client: TestClient, seed_detection, parameters):
    detection_id = seed_detection()

    response = client.get(f"{URL}/{detection_id}/flows", params=parameters)

    assert response.status_code == 422, response.text
    assert all(error["loc"][0] == "query" for error in response.json()["detail"])


def test_database_failure_returns_503_without_connection_details(client: TestClient, monkeypatch):
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        monkeypatch.setenv("DATABASE_URL", f"postgresql://unavailable:private@127.0.0.1:{port}/missing")
        response = client.get(f"{URL}/{uuid4()}/flows")

    assert response.status_code == 503, response.text
    assert response.json() == {"detail": "Database storage unavailable"}
    assert "private" not in response.text


def test_openapi_documents_public_route_query_constraints_and_response(client: TestClient):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][URL + "/{id}/flows"]["get"]
    assert "requestBody" not in operation
    assert operation.get("security", []) == []
    assert {"200", "404", "422", "503"} <= operation["responses"].keys()
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert set(parameters) == {"id", "page", "page_size", "sort_order"}
    assert parameters["id"]["schema"]["format"] == "uuid"
    assert parameters["id"]["in"] == "path"
    assert all(parameters[name]["in"] == "query" for name in ("page", "page_size", "sort_order"))
    assert parameters["page_size"]["schema"]["minimum"] == 1
    assert parameters["page_size"]["schema"]["maximum"] == 500
    assert set(schema["components"]["schemas"]["GetDetectionFlowsResponse"]["required"]) == {
        "items",
        "total",
        "page",
        "page_size",
    }
