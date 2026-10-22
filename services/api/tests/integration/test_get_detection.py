"""Detection details through real HTTP and disposable TimescaleDB."""

import socket
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

URL = "/api/v1/detections"
START = datetime(2026, 1, 1, tzinfo=UTC)
NULLABLE_FIELDS = {
    "configuration_id",
    "first_ingested_at",
    "last_ingested_at",
    "confidence",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "window_size_s",
    "window_start",
    "window_end",
    "explanation",
    "features",
}
RESPONSE_FIELDS = NULLABLE_FIELDS | {"detection_id", "created_at", "type", "method", "severity", "trace_ids"}


def insert_minimal_detection(db: psycopg.Connection):
    detection_id = uuid4()
    db.execute(
        "INSERT INTO detections (detection_id, created_at, type, method, severity) "
        "VALUES (%s, %s, 'port_scan', 'threshold', 'HIGH')",
        (detection_id, START),
    )
    return detection_id


def test_public_detail_returns_requested_record_and_preserves_rows(client: TestClient, db: psycopg.Connection):
    insert_minimal_detection(db)
    detection_id, configuration_id = uuid4(), uuid4()
    first_ingested_at = START - timedelta(seconds=13, microseconds=123456)
    last_ingested_at = START - timedelta(seconds=3, microseconds=654321)
    window_start = START - timedelta(seconds=60)
    features = {"unique_dst_ports": 150, "threshold": 100, "samples": [80, 443]}
    explanation = "Threshold exceeded — scan detected."
    db.execute(
        "INSERT INTO detection_configs (configuration_id, detection_type, method, parameters) "
        "VALUES (%s, 'port_scan', 'threshold', %s)",
        (configuration_id, Jsonb({"threshold": 100})),
    )
    db.execute(
        "INSERT INTO detections (detection_id, configuration_id, created_at, first_ingested_at, "
        "last_ingested_at, type, method, severity, confidence, src_ip, dst_ip, src_port, dst_port, "
        "protocol, window_size_s, window_start, window_end, explanation, features, trace_ids) "
        "VALUES (%s, %s, %s, %s, %s, 'port_scan', 'threshold', 'HIGH', 0.75, "
        "'2001:db8::1', '192.0.2.10', 1234, 443, 'TCP', 60, %s, %s, %s, %s, %s)",
        (
            detection_id,
            configuration_id,
            START,
            first_ingested_at,
            last_ingested_at,
            window_start,
            START,
            explanation,
            Jsonb(features),
            ["trace-1", "trace-2"],
        ),
    )
    before = db.execute("SELECT * FROM detections ORDER BY detection_id").fetchall()

    response = client.get(f"{URL}/{detection_id}")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "detection_id": str(detection_id),
        "configuration_id": str(configuration_id),
        "created_at": "2026-01-01T00:00:00Z",
        "first_ingested_at": first_ingested_at.isoformat().replace("+00:00", "Z"),
        "last_ingested_at": last_ingested_at.isoformat().replace("+00:00", "Z"),
        "type": "port_scan",
        "method": "threshold",
        "severity": "HIGH",
        "confidence": 0.75,
        "src_ip": "2001:db8::1",
        "dst_ip": "192.0.2.10",
        "src_port": 1234,
        "dst_port": 443,
        "protocol": "TCP",
        "window_size_s": 60,
        "window_start": "2025-12-31T23:59:00Z",
        "window_end": "2026-01-01T00:00:00Z",
        "explanation": explanation,
        "features": features,
        "trace_ids": ["trace-1", "trace-2"],
    }
    assert db.execute("SELECT * FROM detections ORDER BY detection_id").fetchall() == before


def test_detail_keeps_nullable_fields_and_empty_trace_ids(client: TestClient, db: psycopg.Connection):
    detection_id = insert_minimal_detection(db)

    response = client.get(f"{URL}/{detection_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert all(body[field] is None for field in NULLABLE_FIELDS)
    assert body["trace_ids"] == []


@pytest.mark.parametrize("field", ["first_ingested_at", "last_ingested_at"])
def test_detail_allows_independently_missing_ingestion_timestamps(client: TestClient, db: psycopg.Connection, field):
    detection_id = insert_minimal_detection(db)
    timestamp = START - timedelta(seconds=3)
    # SQL identifiers come from the fixed parametrization above, never an HTTP request.
    db.execute(
        psycopg.sql.SQL("UPDATE detections SET {} = %s WHERE detection_id = %s").format(psycopg.sql.Identifier(field)),
        (timestamp, detection_id),
    )

    response = client.get(f"{URL}/{detection_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert datetime.fromisoformat(body[field]) == timestamp
    other = "last_ingested_at" if field == "first_ingested_at" else "first_ingested_at"
    assert body[other] is None


def test_unknown_detection_returns_404_even_when_other_records_exist(client: TestClient, db: psycopg.Connection):
    insert_minimal_detection(db)

    response = client.get(f"{URL}/{uuid4()}")

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Detection not found"}


@pytest.mark.parametrize("identifier", ["not-a-uuid", "123", "550e8400-e29b-41d4-a716-44665544000g"])
def test_invalid_uuid_returns_path_validation_error(client: TestClient, identifier: str):
    response = client.get(f"{URL}/{identifier}")

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["path", "id"]


def test_unavailable_database_returns_503_without_connection_details(client: TestClient, monkeypatch):
    # Real connection refusal on a reserved, non-listening port; no dependency overrides.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        monkeypatch.setenv("DATABASE_URL", f"postgresql://unavailable:private@127.0.0.1:{port}/missing")
        response = client.get(f"{URL}/{uuid4()}")

    assert response.status_code == 503, response.text
    assert response.json() == {"detail": "Database storage unavailable"}
    assert "private" not in response.text


def test_openapi_describes_public_uuid_route_and_nullable_response(client: TestClient):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][URL + "/{id}"]["get"]

    assert "requestBody" not in operation
    assert operation.get("security", []) == []
    assert {"200", "404", "422", "503"} <= operation["responses"].keys()
    assert operation["parameters"][0]["in"] == "path"
    assert operation["parameters"][0]["name"] == "id"
    assert operation["parameters"][0]["schema"]["format"] == "uuid"
    response_schema = schema["components"]["schemas"]["GetDetectionResponse"]
    assert set(response_schema["required"]) == RESPONSE_FIELDS
    for field in NULLABLE_FIELDS:
        assert {"type": "null"} in response_schema["properties"][field]["anyOf"]
