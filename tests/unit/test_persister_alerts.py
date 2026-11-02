"""Persister side of F17: which detection messages become alert rows, and the `alert` field of the contract."""

import copy

import pytest
from persister import ALERT_SQL, DET_SQL, alert_row

from netguard_common import SchemaError, detection_id, validate_detection

DET = {
    "schema_version": 1,
    "detection_id": detection_id("port_scan", "rule", "10.66.6.6", "10.1.0.1", 1_760_000_000.0, 10),
    "trace_ids": ["t-1234567"],
    "created_at": 1_760_000_011.0,
    "first_ingested_at": 1_760_000_001.0,
    "last_ingested_at": 1_760_000_002.0,
    "type": "port_scan",
    "method": "rule",
    "severity": "MEDIUM",
    "confidence": 0.66,
    "src_ip": "10.66.6.6",
    "dst_ip": "10.1.0.1",
    "window": {"size_s": 10, "start": 1_760_000_000.0, "end": 1_760_000_010.0},
    "features": {"unique_dst_ports": 160, "threshold": 100},
    "explanation": "10.66.6.6 contacted 160 distinct destination ports.",
    "alert": True,
}


def test_alert_field_is_optional_boolean():
    validate_detection(DET)
    without = {k: v for k, v in DET.items() if k != "alert"}
    validate_detection(without)
    with pytest.raises(SchemaError, match="alert"):
        validate_detection({**DET, "alert": "yes"})


def test_alert_id_is_deterministic():
    """Redelivered detection -> same alert_id -> no duplicate alert (NFR04)."""
    a, b = alert_row(DET), alert_row(copy.deepcopy(DET))
    assert a == b and a[1] == DET["detection_id"]
    assert alert_row({**DET, "detection_id": detection_id("dos", "rule", None, "10.1.0.1", 0, 1)})[0] != a[0]


def test_sql_is_idempotent_and_only_escalates():
    assert "ON CONFLICT (detection_id) DO NOTHING" in ALERT_SQL
    assert "ON CONFLICT (detection_id) DO UPDATE" in DET_SQL
    assert "EXCLUDED.severity) > array_position" in DET_SQL  # never downgrades
    assert "created_at =" not in DET_SQL.split("DO UPDATE")[1]  # latency stays measured to the first detection
