"""Health check and the public detections list through real HTTP and TimescaleDB."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

START = datetime(2026, 1, 1, tzinfo=UTC)
DASHBOARD_FIELDS = {"detection_id", "created_at", "type", "severity", "src_ip", "explanation"}


def insert_detection(db: psycopg.Connection, created_at: datetime, src_ip: str) -> None:
    db.execute(
        "INSERT INTO detections (detection_id, created_at, type, method, severity, confidence, src_ip, features, "
        "explanation) VALUES (%s, %s, 'port_scan', 'rule', 'HIGH', 0.8, %s, %s, 'test scan')",
        (uuid4(), created_at, src_ip, Jsonb({"unique_dst_ports": 300})),
    )


def test_health_reports_the_database(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "db": "ok"}


def test_detections_are_listed_newest_first(client: TestClient, db: psycopg.Connection) -> None:
    """API-01"""
    for minutes in (0, 2, 1):
        insert_detection(db, START + timedelta(minutes=minutes), src_ip=f"10.66.6.{minutes + 1}")

    response = client.get("/api/v1/detections", params={"limit": 2})

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["page"], body["page_size"]) == (3, 1, 2)
    detections = body["items"]
    assert [detection["src_ip"] for detection in detections] == ["10.66.6.3", "10.66.6.2"]
    assert DASHBOARD_FIELDS <= detections[0].keys()


@pytest.mark.parametrize("limit", ["0", "-1", "501", "abc"])
def test_invalid_limit_is_rejected(client: TestClient, limit: str) -> None:
    """API-02"""
    assert client.get("/api/v1/detections", params={"limit": limit}).status_code == 422
