"""Broker-free tests: simulator output -> processor windows -> detection that passes the schema."""

from processor import WindowState, port_scan_rule
from simulator import generate, normal_flow, port_scan_flow

from netguard_common import validate_detection, validate_flow

T0 = 1_760_000_000.0  # aligned to a 10 s boundary


def test_simulator_flows_match_schema():
    """UT-05"""
    for f in generate(["normal", "port_scan"], 500, T0):
        validate_flow(f)


def test_port_scan_detected_and_valid():
    """UT-07"""
    ws = WindowState(size_s=10)
    for _ in range(300):
        ws.add(port_scan_flow(T0 + 1, "10.66.6.6", "10.1.0.1"))
    closed = ws.pop_closed(now=T0 + 12)
    assert len(closed) == 1
    src, start, w = closed[0]
    det = port_scan_rule(src, start, w, 10, threshold=100, now=T0 + 12)
    assert det is not None
    validate_detection(det)
    assert det["src_ip"] == "10.66.6.6"
    assert det["features"]["unique_dst_ports"] > 100
    assert det["severity"] in {"MEDIUM", "HIGH", "CRITICAL", "LOW"}


def test_first_and_last_ingested_at():
    """UT-07: NFR02 latency is measured from last_ingested_at, time to detect from first_ingested_at."""
    ws = WindowState(size_s=10)
    for port, ingested_at in [(1, T0 + 1), (2, T0 + 5), (3, T0 + 3)]:
        flow = port_scan_flow(T0 + 1, "10.66.6.6", "10.1.0.1")
        flow.update(dst_port=port, ingested_at=ingested_at)
        ws.add(flow)
    ((src, start, w),) = ws.pop_closed(T0 + 12)
    det = port_scan_rule(src, start, w, 10, threshold=3, now=T0 + 12)
    assert (det["first_ingested_at"], det["last_ingested_at"]) == (T0 + 1, T0 + 5)


def test_normal_traffic_no_detection():
    """UT-08"""
    ws = WindowState(size_s=10)
    for _ in range(2000):
        ws.add(normal_flow(T0 + 1))
    dets = [port_scan_rule(s, st, w, 10, 100, T0 + 12) for s, st, w in ws.pop_closed(T0 + 12)]
    assert not any(dets)


def test_open_window_not_closed_early():
    """UT-06"""
    ws = WindowState(size_s=10, grace_s=1)
    ws.add(port_scan_flow(T0 + 5, "10.66.6.6", "10.1.0.1"))
    assert ws.pop_closed(now=T0 + 10.5) == []
    assert len(ws.pop_closed(now=T0 + 11)) == 1


def test_duplicate_flows_give_same_detection_id():
    """UT-09"""

    def run():
        ws = WindowState(size_s=10)
        for p in range(150):
            f = port_scan_flow(T0 + 1, "10.66.6.6", "10.1.0.1")
            f["dst_port"] = p + 1
            ws.add(f)
        ((s, st, w),) = ws.pop_closed(T0 + 12)
        return port_scan_rule(s, st, w, 10, 100, T0 + 12)["detection_id"]

    assert run() == run()
