"""Pipeline contracts against real TimescaleDB, including persister SQL and dedupe."""

import socket
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
import pytest
from app.domain.network_flow import NetworkFlow
from app.infrastructure.persistence.mappings import configure_mappings
from fastapi.testclient import TestClient
from persister import FLOW_INSERT_SQL, flow_row
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_health_checks_database_without_authentication(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}
    assert client.get("/health/ping").json() == {"status": "ok"}


def test_health_reports_database_outage_but_ping_stays_available(client: TestClient, monkeypatch) -> None:
    # Reserve a real local port without listening: connections are refused, no database mock.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        monkeypatch.setenv("DATABASE_URL", f"postgresql://unavailable:private@127.0.0.1:{port}/missing")
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "unavailable"}
    assert "private" not in response.text
    assert client.get("/health/ping").status_code == 200


def test_detections_preserve_public_list_contract_and_limit(client: TestClient, db: psycopg.Connection) -> None:
    assert client.get("/api/v1/detections").json() == {"items": [], "total": 0, "page": 1, "page_size": 50}
    identifiers = [uuid4() for _ in range(55)]
    for index, detection_id in enumerate(identifiers):
        db.execute(
            "INSERT INTO detections (detection_id, created_at, type, method, severity, confidence, "
            "src_ip, dst_ip, window_size_s, features, explanation) "
            "VALUES (%s, %s, 'port_scan', 'threshold', 'HIGH', 0.9, '10.1.2.3', '2001:db8::1', "
            "10, '{\"unique_dst_ports\": 150}'::jsonb, 'Port scan detected')",
            (detection_id, START + timedelta(seconds=index)),
        )

    response = client.get("/api/v1/detections")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["page"], body["page_size"]) == (55, 1, 50)
    assert len(body["items"]) == 50
    assert [item["detection_id"] for item in body["items"]] == [str(value) for value in reversed(identifiers[5:])]
    item = client.get("/api/v1/detections", params={"limit": 1}).json()["items"][0]
    assert set(item) == {
        "detection_id",
        "created_at",
        "type",
        "method",
        "severity",
        "confidence",
        "src_ip",
        "dst_ip",
        "window_size_s",
        "features",
        "explanation",
    }
    assert item["src_ip"] == "10.1.2.3"
    assert item["dst_ip"] == "2001:db8::1"
    assert item["features"] == {"unique_dst_ports": 150}
    assert item["confidence"] == 0.9
    assert len(client.get("/api/v1/detections", params={"limit": 500}).json()["items"]) == 55


def test_detections_allow_nullable_evidence_and_order_timestamp_ties(
    client: TestClient, db: psycopg.Connection
) -> None:
    identifiers = sorted([uuid4(), uuid4()], reverse=True)
    for detection_id in identifiers:
        db.execute(
            "INSERT INTO detections (detection_id, created_at, type, method, severity) "
            "VALUES (%s, %s, 'port_scan', 'threshold', 'HIGH')",
            (detection_id, START),
        )
    response = client.get("/api/v1/detections")
    assert response.status_code == 200, response.text
    assert [row["detection_id"] for row in response.json()["items"]] == [str(value) for value in identifiers]
    assert response.json()["items"][0]["src_ip"] is None
    assert response.json()["items"][0]["features"] is None


@pytest.mark.parametrize("limit", [0, 501, -1, "invalid"])
def test_detections_reject_invalid_limit(client: TestClient, limit) -> None:
    assert client.get("/api/v1/detections", params={"limit": limit}).status_code == 422


def test_persister_writes_labels_and_deduplicates_composite_key(db: psycopg.Connection, database_url: str) -> None:
    flow = {
        "flow_id": str(uuid4()),
        "trace_id": "pipeline-compatibility",
        "ingested_at": START.timestamp() + 1,
        "ts_start": START.timestamp(),
        "duration_ms": 100.0,
        "src_ip": "10.1.2.3",
        "dst_ip": "10.1.2.4",
        "src_port": 12345,
        "dst_port": 443,
        "protocol": "TCP",
        "packets": 5,
        "bytes": 1000,
        "tcp_flags": "S",
        "source": "simulator",
        "label": "port_scan",
    }
    unlabelled = {key: value for key, value in flow.items() if key != "label"}
    unlabelled["ts_start"] += 10
    with db.cursor() as cursor:
        cursor.executemany(FLOW_INSERT_SQL, [flow_row(flow), flow_row(flow), flow_row(unlabelled)])
    rows = db.execute("SELECT ts_start, label, trace_id FROM network_flows ORDER BY ts_start").fetchall()
    assert rows == [(START, "port_scan", flow["trace_id"]), (START + timedelta(seconds=10), None, flow["trace_id"])]

    configure_mappings()
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://", 1))
    try:
        with Session(engine) as session:
            stored = session.scalar(select(NetworkFlow).where(NetworkFlow.ts_start == START))
            assert stored.flow_id == UUID(flow["flow_id"])
            assert stored.label == "port_scan"
    finally:
        engine.dispose()
