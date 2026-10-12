import copy

import pytest

from netguard_common import SchemaError, detection_id, flow_id_for, validate_detection, validate_flow

FLOW = {
    "schema_version": 1, "flow_id": "3f2b8a51-6a0e-4a2e-9a6f-2a1f0b0c1d2e", "trace_id": "abcdef0123456789",
    "ingested_at": 1760000000.5, "ts_start": 1760000000.0, "duration_ms": 12.5,
    "src_ip": "10.0.0.1", "dst_ip": "10.1.0.1", "src_port": 51000, "dst_port": 443,
    "protocol": "TCP", "packets": 10, "bytes": 4200, "tcp_flags": "SA", "source": "simulator", "label": "normal",
}


def test_valid_flow_passes():
    assert validate_flow(copy.deepcopy(FLOW))


@pytest.mark.parametrize("field,value", [
    ("dst_port", 70000), ("src_ip", "not-an-ip"), ("protocol", "HTTP"),
    ("packets", -1), ("tcp_flags", "XYZ"), ("label", "evil"),
])
def test_invalid_flow_fields_rejected(field, value):
    f = copy.deepcopy(FLOW)
    f[field] = value
    with pytest.raises(SchemaError, match=field):
        validate_flow(f)


def test_missing_required_field_rejected():
    f = copy.deepcopy(FLOW)
    del f["trace_id"]
    with pytest.raises(SchemaError):
        validate_flow(f)


def test_unknown_field_rejected():
    with pytest.raises(SchemaError):
        validate_flow({**FLOW, "surprise": 1})


def test_flow_id_deterministic():
    assert flow_id_for("a.pcap", 7) == flow_id_for("a.pcap", 7)
    assert flow_id_for("a.pcap", 7) != flow_id_for("a.pcap", 8)


def test_detection_id_deterministic_for_duplicates():
    a = detection_id("port_scan", "rule", "10.0.0.1", None, 1760000000.0, 10)
    b = detection_id("port_scan", "rule", "10.0.0.1", None, 1760000000.0, 10)
    c = detection_id("port_scan", "rule", "10.0.0.1", None, 1760000010.0, 10)
    assert a == b != c


def test_detection_schema_rejects_bad_severity_and_confidence():
    det = {
        "schema_version": 1, "detection_id": detection_id("dos", "rule", "a", "b", 0, 1),
        "trace_ids": ["t1"], "created_at": 2.0, "first_ingested_at": 1.0, "type": "dos", "method": "rule",
        "severity": "HIGH", "confidence": 0.9, "src_ip": "10.0.0.1", "dst_ip": "10.1.0.1",
        "window": {"size_s": 1, "start": 0, "end": 1}, "features": {"conn": 900}, "explanation": "x",
    }
    validate_detection(det)
    with pytest.raises(SchemaError):
        validate_detection({**det, "severity": "SEVERE"})
    with pytest.raises(SchemaError):
        validate_detection({**det, "confidence": 1.5})
