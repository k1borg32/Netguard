"""Unit tests for the flow-file importer (services/importer).

Covers IT-03 (a file row becomes a valid flow.v1) and SEC-02 (malformed rows
are rejected, not published). See Docs/TestPlan.
"""

import importlib.util
import pathlib
import time

import pytest

from netguard_common.messages import validate_flow

_PATH = pathlib.Path(__file__).resolve().parents[2] / "services" / "importer" / "importer.py"
_spec = importlib.util.spec_from_file_location("importer", _PATH)
importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importer)

GOOD_ROW = {
    "ts_start": "1700000000.0",
    "duration_ms": "12.5",
    "src_ip": "10.0.0.5",
    "dst_ip": "10.0.0.9",
    "src_port": "4444",
    "dst_port": "80",
    "protocol": "6",
    "packets": "8",
    "bytes": "640",
    "tcp_flags": "SA",
    "label": "benign",
}


def test_normalise_row_maps_fields():
    """IT-03: numeric protocol -> enum, ports -> int, 'benign' -> normal."""
    out = importer.normalise_row(GOOD_ROW)
    assert out["protocol"] == "TCP"
    assert out["src_port"] == 4444
    assert out["label"] == "normal"
    assert out["ts_start"] == 1700000000.0


def test_build_flow_passes_schema():
    """IT-03: a built flow validates against flow.v1.json and is a flowfile."""
    flow = importer.build_flow(GOOD_ROW, "sample.csv", 0, time.time(), "trace123456")
    validate_flow(flow)
    assert flow["source"] == "flowfile"
    assert flow["schema_version"] == 1


def test_flow_id_is_deterministic():
    """Same file+index -> same flow_id, so replays dedupe."""
    a = importer.build_flow(GOOD_ROW, "sample.csv", 3, time.time(), "t1abcdef")
    b = importer.build_flow(GOOD_ROW, "sample.csv", 3, time.time(), "t2abcdef")
    assert a["flow_id"] == b["flow_id"]


def test_iso_timestamp_accepted():
    out = importer.normalise_row(dict(GOOD_ROW, ts_start="2023-11-14T22:13:20"))
    assert isinstance(out["ts_start"], float)


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD_ROW, "src_port": "notaport"},
        {**GOOD_ROW, "label": "definitely_not_a_label"},
        {k: v for k, v in GOOD_ROW.items() if k != "src_ip"},
    ],
)
def test_bad_row_is_rejected(bad):
    """SEC-02: malformed rows raise, so the importer drops them instead of publishing."""
    with pytest.raises(ValueError):
        validate_flow(importer.build_flow(bad, "sample.csv", 0, time.time(), "trace123456"))
