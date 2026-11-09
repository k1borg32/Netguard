"""DQ-06: hard cases for the detection engine at the default thresholds of config/detection.yaml.

Not all of them are detected, the tests pin down what the engine does today so a change in the windows or thresholds
shows up here. Results and explanation: Docs/TestReport, section 3.
"""

from pathlib import Path

import yaml
from detection_engine import DetectionEngine, parse_config

T0 = 1_760_000_040.0  # aligned to a 60 s boundary
CONFIG = parse_config(yaml.safe_load((Path(__file__).resolve().parents[2] / "config" / "detection.yaml").read_text()))
SCANNER = "10.0.0.66"
SERVER = "10.1.0.1"


def flow(ts, src=SCANNER, dport=443):
    return {
        "schema_version": 1,
        "flow_id": f"{src}-{ts}-{dport}",
        "trace_id": f"{src}-{ts}-{dport}",
        "ingested_at": ts,
        "ts_start": ts,
        "duration_ms": 10.0,
        "src_ip": src,
        "dst_ip": SERVER,
        "src_port": 40000,
        "dst_port": dport,
        "protocol": "TCP",
        "packets": 5,
        "bytes": 500,
        "tcp_flags": "S",
        "source": "flowfile",
        "label": "normal",
    }


def detect(flows, until):
    """Flows in time order like live traffic (wall clock = flow time), then everything closed at `until`."""
    engine = DetectionEngine(CONFIG)
    for f in sorted(flows, key=lambda f: f["ts_start"]):
        engine.add(f, f["ts_start"])
    return engine.evaluate(until)


def test_scan_split_across_two_windows_is_missed():
    """DQ-06: 120 ports in 10 s, but starting in the middle of a 10 s window, so each window sees 60 ports and the
    threshold is 100. Tumbling windows can miss a scan of up to twice the threshold. The same scan inside one
    window is found."""
    split = [flow(T0 + 5 + i / 12, dport=1 + i) for i in range(120)]
    assert detect(split, until=T0 + 120) == []

    inside = [flow(T0 + i / 12, dport=1 + i) for i in range(120)]
    assert [d["type"] for d in detect(inside, until=T0 + 120)] == ["port_scan"]


def test_scan_just_below_the_threshold_is_missed():
    """DQ-06: 99 new ports in every 10 s window for a minute, 594 ports in total, and no rule fires."""
    slow = [flow(T0 + 10 * k + j / 10, dport=1 + 99 * k + j) for k in range(6) for j in range(99)]
    assert detect(slow, until=T0 + 120) == []


def test_slow_scan_of_a_known_host_is_unknown():
    """DQ-06: a host that made one connection per second to port 443 for 12 minutes now makes one per second to a
    new port. Far too slow for the port scan rule (10 ports per 10 s), but the z-score method sees the jump in
    distinct ports at the same volume and reports `unknown` for that minute."""
    history = [flow(T0 + s) for s in range(12 * 60)]
    scan = [flow(T0 + 720 + s, dport=1000 + s) for s in range(60)]
    found = detect(history + scan, until=T0 + 900)
    assert [(d["type"], d["method"], d["window"]["start"]) for d in found] == [("unknown", "statistical", T0 + 720)]
    assert found[0]["features"]["feature"] == "unique_dst_ports"


def test_scan_hidden_in_heavy_traffic_is_found():
    """DQ-06: a 150-port scan of a server while 100 clients send the same server 2,000 normal flows in the same
    10 s. The rule counts per source, so the other traffic doesn't hide the scan."""
    busy = [flow(T0 + i / 200, src=f"10.0.1.{i % 100 + 1}") for i in range(2000)]
    scan = [flow(T0 + i / 15, dport=1 + i) for i in range(150)]
    found = detect(busy + scan, until=T0 + 120)
    assert [(d["type"], d["src_ip"], d["features"]["unique_dst_ports"]) for d in found] == [("port_scan", SCANNER, 150)]
