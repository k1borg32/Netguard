"""Broker-free tests: simulator output -> detection engine windows -> detection that passes the schema."""

from pathlib import Path

from detection_engine import DetectionEngine, load_config
from simulator import generate, normal_flow, port_scan_flow

from netguard_common import validate_detection, validate_flow

T0 = 1_760_000_040.0  # aligned to a 60 s (and so 10 s and 1 s) boundary
CONFIG = Path(__file__).resolve().parents[2] / "config" / "detection.yaml"


def engine() -> DetectionEngine:
    return DetectionEngine(load_config(str(CONFIG)))


def scan(e: DetectionEngine, ports: int, ts: float = T0 + 1, wall: float = T0 + 1) -> None:
    for p in range(1, ports + 1):
        f = port_scan_flow(ts, "10.66.6.6", "10.1.0.1")
        f["dst_port"] = p
        e.add(f, wall)


def test_simulator_flows_match_schema():
    """UT-05"""
    for f in generate(["normal", "port_scan"], 500, T0):
        validate_flow(f)


def test_port_scan_detected_and_valid():
    """UT-07: port scan above the threshold, with its evidence (F09)."""
    e = engine()
    scan(e, 300)
    dets = [d for d in e.evaluate(T0 + 12) if d["type"] == "port_scan"]
    assert len(dets) == 1
    det = dets[0]
    validate_detection(det)
    assert det["src_ip"] == "10.66.6.6"
    assert det["dst_ip"] == "10.1.0.1"
    assert det["features"]["unique_dst_ports"] == 300
    assert det["features"]["threshold"] == 100
    assert det["window"] == {"size_s": 10, "start": T0, "end": T0 + 10}
    assert det["severity"] == "HIGH"  # 300 / 100 = 3.0
    assert "300 distinct destination ports" in det["explanation"]


def test_first_and_last_ingested_at():
    """UT-07: NFR02 latency is measured from last_ingested_at, time to detect from first_ingested_at."""
    e = engine()
    for port in range(1, 101):
        flow = port_scan_flow(T0 + 1, "10.66.6.6", "10.1.0.1")
        flow.update(dst_port=port, ingested_at=T0 + 1 + (4 if port == 50 else 0))
        e.add(flow, T0 + 1)
    (det,) = e.evaluate(T0 + 12)
    assert (det["first_ingested_at"], det["last_ingested_at"]) == (T0 + 1, T0 + 5)


def test_normal_traffic_no_detection():
    """UT-08"""
    e = engine()
    for _ in range(2000):
        e.add(normal_flow(T0 + 1), T0 + 1)
    assert e.evaluate(T0 + 1) == []
    assert e.evaluate(T0 + 62) == []


def test_open_window_not_closed_early():
    """UT-06: closes after size + grace of flow time, not before."""
    e = engine()
    e.add(port_scan_flow(T0 + 5, "10.66.6.6", "10.1.0.1"), T0 + 5)
    ten = e.sources[10]
    e.evaluate(T0 + 10.5)
    assert len(ten.windows) == 1
    e.evaluate(T0 + 11)
    assert len(ten.windows) == 0


def test_duplicate_flows_give_same_detection_id():
    """UT-09"""

    def run():
        e = engine()
        scan(e, 150)
        return [d["detection_id"] for d in e.evaluate(T0 + 12)]

    assert run() == run()
