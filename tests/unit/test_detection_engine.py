"""Detection engine: windows, rules, z-score method, severity/confidence, config checks and alert policy."""

import copy
import uuid
from pathlib import Path

import pytest
import yaml
from detection_engine import ConfigError, DetectionEngine, parse_config
from detection_engine.scoring import confidence_for, severity_for

from netguard_common import validate_detection

T0 = 1_760_000_040.0  # aligned to a 60 s boundary
RAW = yaml.safe_load((Path(__file__).resolve().parents[2] / "config" / "detection.yaml").read_text())


def cfg(**changes):
    """Repo config with dotted-path overrides, e.g. cfg(**{"rules.dos.ddos_min_sources": 3})."""
    raw = copy.deepcopy(RAW)
    for path, value in changes.items():
        *parents, last = path.split(".")
        node = raw
        for p in parents:
            node = node[p]
        node[last] = value
    return parse_config(raw)


def flow(ts, src="10.0.0.5", dst="10.1.0.1", dport=80, packets=5, label="normal", nbytes=None):
    return {
        "schema_version": 1,
        "flow_id": str(uuid.uuid4()),
        "trace_id": uuid.uuid4().hex,
        "ingested_at": ts,
        "ts_start": ts,
        "duration_ms": 10.0,
        "src_ip": src,
        "dst_ip": dst,
        "src_port": 40000,
        "dst_port": dport,
        "protocol": "TCP",
        "packets": packets,
        "bytes": packets * 100 if nbytes is None else nbytes,
        "tcp_flags": "S",
        "source": "simulator",
        "label": label,
    }


def feed(e, flows):
    """Add flows like live traffic: the wall clock is the flow time."""
    for f in flows:
        e.add(f, f["ts_start"])


def run(e, flows, until):
    feed(e, flows)
    return e.evaluate(until)


def types(dets):
    return sorted(d["type"] for d in dets)


# ---- windows (F05) ----


def test_flows_on_window_boundaries():
    """UT-13: a flow at the end of a window belongs to it, a flow at the next start to the next one."""
    e = DetectionEngine(cfg())
    feed(e, [flow(T0 + 9.999), flow(T0 + 10.0)])
    for size, starts in {1: {T0 + 9, T0 + 10}, 10: {T0, T0 + 10}, 60: {T0}}.items():
        assert {s for _, s in e.sources[size].windows} == starts, size


def test_late_flow_counted_not_added():
    """UT-13: a flow for a window that has already closed is dropped and counted."""
    e = DetectionEngine(cfg())
    e.add(flow(T0 + 1), T0 + 1)
    e.evaluate(T0 + 15)  # 10 s window [T0, T0+10) closed
    e.add(flow(T0 + 2), T0 + 15)
    assert e.sources[10].late_flows == 1
    assert e.sources[60].late_flows == 0  # still open there
    assert e.stats()["late_flows"] == 1


def test_one_source_ahead_in_time_does_not_close_another():
    """Each source has its own clock: a fast partition doesn't make a slow one late (PCAP import)."""
    e = DetectionEngine(cfg())
    e.add(flow(T0 + 1, src="10.0.0.1", dst="10.1.0.1"), T0)
    e.add(flow(T0 + 500, src="10.0.0.2", dst="10.1.0.2"), T0)
    e.evaluate(T0)
    assert e.add(flow(T0 + 2, src="10.0.0.1", dst="10.1.0.1"), T0)
    assert e.stats()["late_flows"] == 0


def test_replayed_old_capture_is_windowed_by_flow_time():
    """Windows use ts_start, so a capture from the past is analysed like live traffic."""
    e = DetectionEngine(cfg())
    old = T0 - 86_400 * 365
    dets = run(e, [flow(old + 1, dport=p) for p in range(1, 201)], until=T0)
    assert e.evaluate(T0 + 15) == []  # nothing left
    scan = [d for d in dets if d["type"] == "port_scan"]
    assert scan and scan[0]["window"]["start"] == old


def test_bad_flow_is_skipped():
    e = DetectionEngine(cfg())
    bad = flow(T0)
    del bad["packets"]
    assert not e.add(bad, T0)
    assert e.stats()["bad_flows"] == 1
    assert e.sources[10].windows == {}


# ---- rules (F06) ----


def test_port_scan_fires_before_window_closes():
    """NFR02: a rule fires as soon as the threshold is crossed, not when the window ends."""
    e = DetectionEngine(cfg())
    dets = run(e, [flow(T0 + 1, dport=p) for p in range(1, 101)], until=T0 + 2)
    assert types(dets) == ["port_scan"]
    assert dets[0]["severity"] == "LOW"


def test_escalation_resends_same_detection_once_per_level():
    e = DetectionEngine(cfg())
    first = run(e, [flow(T0 + 1, dport=p) for p in range(1, 101)], until=T0 + 2)
    same = run(e, [flow(T0 + 2, dport=p) for p in range(101, 120)], until=T0 + 3)
    higher = run(e, [flow(T0 + 3, dport=p) for p in range(120, 301)], until=T0 + 4)
    assert same == []
    assert [d["severity"] for d in higher] == ["HIGH"]
    assert higher[0]["detection_id"] == first[0]["detection_id"]
    assert e.evaluate(T0 + 12) == []  # closing doesn't repeat it


def test_dos_from_one_source():
    """UT-14: DoS-like, connections path; silent just below the threshold."""
    below = run(DetectionEngine(cfg()), [flow(T0 + 0.5) for _ in range(499)], until=T0 + 3)
    above = run(DetectionEngine(cfg()), [flow(T0 + 0.5) for _ in range(500)], until=T0 + 3)
    assert "dos" not in types(below)
    (dos,) = [d for d in above if d["type"] == "dos"]
    assert (dos["src_ip"], dos["dst_ip"], dos["window"]["size_s"]) == ("10.0.0.5", "10.1.0.1", 1)
    assert dos["features"]["triggered_by"] == "connections"


def test_dos_by_packets():
    """UT-14: DoS-like, packets path (spec 9.1: 'connections or packets')."""
    dets = run(DetectionEngine(cfg()), [flow(T0 + 0.5, packets=2000) for _ in range(10)], until=T0 + 3)
    (dos,) = [d for d in dets if d["type"] == "dos"]
    assert dos["features"]["triggered_by"] == "packets"
    assert dos["features"]["packets"] == 20000


def test_ddos_from_many_sources():
    """UT-14: many sources together -> one target; source is null."""
    flows = [flow(T0 + 0.5, src=f"10.9.0.{i % 20 + 1}") for i in range(600)]
    dets = run(DetectionEngine(cfg()), flows, until=T0 + 3)
    (dos,) = [d for d in dets if d["type"] == "dos"]
    assert dos["src_ip"] is None and dos["dst_ip"] == "10.1.0.1"
    assert dos["features"]["unique_src_ips"] == 20
    validate_detection(dos)


def test_ddos_needs_enough_sources():
    flows = [flow(T0 + 0.5, src=f"10.9.0.{i % 5 + 1}") for i in range(600)]
    assert "dos" not in types(run(DetectionEngine(cfg()), flows, until=T0 + 3))


def test_brute_force():
    """UT-14: repeated attempts to one login service; other ports don't count."""
    ssh = [flow(T0 + i, dport=22) for i in range(50)]
    web = [flow(T0 + i, dport=80) for i in range(50)]
    assert "brute_force" not in types(run(DetectionEngine(cfg()), ssh[:49] + web, until=T0 + 62))
    (bf,) = [d for d in run(DetectionEngine(cfg()), ssh, until=T0 + 62) if d["type"] == "brute_force"]
    assert bf["features"]["dst_port"] == 22 and bf["features"]["attempts"] == 50


def test_suspicious_pattern_new_hosts():
    """UT-14: abnormal connection pattern = many hosts outside the source's recent profile."""
    sweep = [flow(T0 + i * 0.5, dst=f"10.2.{i // 250}.{i % 250 + 1}") for i in range(60)]
    (sp,) = [d for d in run(DetectionEngine(cfg()), sweep, until=T0 + 62) if d["type"] == "suspicious_pattern"]
    assert sp["features"]["new_dst_ips"] == 60


def test_suspicious_pattern_ignores_known_hosts():
    """Hosts from the last profile_window_s are not new, so a source's usual servers never trigger it."""
    e = DetectionEngine(cfg())
    hosts = [f"10.2.0.{i}" for i in range(1, 61)]
    run(e, [flow(T0 + i * 0.5, dst=h) for i, h in enumerate(hosts)], until=T0 + 62)
    again = run(e, [flow(T0 + 60 + i * 0.5, dst=h) for i, h in enumerate(hosts)], until=T0 + 122)
    assert "suspicious_pattern" not in types(again)


# ---- statistical method (F07) ----


def steady(e, windows, per_window=30, src="10.0.0.5", start=T0):
    """`windows` windows of normal traffic from one source; returns the detections."""
    out = []
    for k in range(windows):
        ws = start + 60 * k
        out += run(e, [flow(ws + i * 60 / per_window, src=src) for i in range(per_window)], until=ws + 61.5)
    return out


def test_no_statistical_result_before_baseline():
    """UT-15: nothing before min_baseline_windows windows of history."""
    e = DetectionEngine(cfg())
    assert steady(e, 9) == []
    spike = [flow(T0 + 540 + i * 0.1) for i in range(400)]
    assert "abnormal_traffic" not in types(run(e, spike, until=T0 + 601.5))


def test_abnormal_traffic_after_baseline():
    """UT-15: a volume far above the source's own history -> abnormal_traffic."""
    e = DetectionEngine(cfg())
    assert steady(e, 10) == []
    spike = [flow(T0 + 600 + i * 0.15) for i in range(400)]
    dets = run(e, spike, until=T0 + 661.5)
    (ab,) = [d for d in dets if d["type"] == "abnormal_traffic"]
    assert ab["method"] == "statistical"
    assert ab["features"]["baseline_windows"] == 10
    assert ab["features"]["zscore"] >= 3.0
    assert "z-score" in ab["explanation"]
    validate_detection(ab)


def test_unknown_when_only_structure_changes():
    """UT-15: same volume, different connection structure, no rule -> unknown."""
    e = DetectionEngine(cfg())
    steady(e, 10)
    odd = [flow(T0 + 600 + i * 2, dport=1000 + i) for i in range(30)]
    dets = run(e, odd, until=T0 + 661.5)
    assert types(dets) == ["unknown"]
    assert dets[0]["features"]["feature"] == "unique_dst_ports"


def test_rule_wins_over_statistical():
    """A port scan from a source with history is a port_scan, not also abnormal_traffic or unknown."""
    e = DetectionEngine(cfg())
    steady(e, 10)
    scan = [flow(T0 + 601, dport=p) for p in range(1, 201)]
    assert types(run(e, scan, until=T0 + 661.5)) == ["port_scan"]


def test_history_restarts_after_long_silence():
    e = DetectionEngine(cfg())
    steady(e, 10)
    later = T0 + 60 * 25  # quiet for longer than the 10-window history
    spike = [flow(later + i * 0.15) for i in range(400)]
    assert "abnormal_traffic" not in types(run(e, spike, until=later + 61.5))


# ---- severity and confidence (spec 9.3) ----


@pytest.mark.parametrize(
    "ratio,expected",
    [
        (1.0, "LOW"),
        (1.49, "LOW"),
        (1.5, "MEDIUM"),
        (2.99, "MEDIUM"),
        (3.0, "HIGH"),
        (5.0, "CRITICAL"),
        (40, "CRITICAL"),
    ],
)
def test_severity_follows_config(ratio, expected):
    """UT-16"""
    assert severity_for(ratio, cfg().severity) == expected


def test_confidence_range_and_order():
    """UT-16: within 0-1, grows with the ratio, rule > statistical > unknown at the same ratio."""
    for r in (1, 2, 5, 100):
        rule = confidence_for(r, "rule", "dos")
        stat = confidence_for(r, "statistical", "abnormal_traffic")
        unk = confidence_for(r, "statistical", "unknown")
        assert 0 <= unk < stat < rule <= 1
    assert confidence_for(1, "rule", "dos") < confidence_for(3, "rule", "dos")


# ---- configuration (UT-17) ----


def test_repo_config_is_valid():
    """UT-17"""
    c = cfg()
    assert c.windows_s == (1, 10, 60)
    assert c.alerts.min_for("unknown") == "HIGH" and c.alerts.min_for("dos") == "MEDIUM"


@pytest.mark.parametrize(
    "change,message",
    [
        ({"rules.port_scan.unique_dst_ports_threshold": 0}, "rules.port_scan.unique_dst_ports_threshold"),
        ({"rules.port_scan.unique_dst_ports_threshold": "100"}, "expected an integer"),
        ({"rules.dos.window_s": 5}, "rules.dos.window_s"),
        ({"windows_s": [1, 10]}, "F05"),
        ({"severity.HIGH": 1.2}, "increase"),
        ({"statistical.method": "isolation_forest"}, "only 'zscore'"),
        ({"statistical.min_baseline_windows": 11}, "don't fit"),
        ({"alerts.min_severity": "SEVERE"}, "alerts.min_severity"),
        ({"alerts.min_severity_by_type": {"portscan": "HIGH"}}, "unknown detection type"),
        ({"rules.brute_force.services": []}, "rules.brute_force.services"),
    ],
)
def test_invalid_config_rejected(change, message):
    """UT-17: invalid values stop the start with an error that names the field."""
    with pytest.raises(ConfigError, match=message):
        cfg(**change)


def test_missing_section_rejected():
    raw = copy.deepcopy(RAW)
    del raw["alerts"]
    with pytest.raises(ConfigError, match="alerts"):
        parse_config(raw)


# ---- alerts (F17) ----


def scan_at(e, start, ports):
    return [d for d in run(e, [flow(start + 1, dport=p) for p in range(1, ports + 1)], until=start + 12)]


def test_low_detection_is_stored_but_no_alert():
    (det,) = scan_at(DetectionEngine(cfg()), T0, 120)  # ratio 1.2 -> LOW
    assert det["severity"] == "LOW" and det["alert"] is False
    validate_detection(det)


def test_medium_detection_raises_alert():
    (det,) = scan_at(DetectionEngine(cfg()), T0, 160)
    assert det["severity"] == "MEDIUM" and det["alert"] is True


@pytest.mark.parametrize("ports,severity,alert", [(6, "MEDIUM", False), (11, "HIGH", True)])
def test_unknown_needs_high(ports, severity, alert):
    """`unknown` uses min_severity_by_type (HIGH), not the default MEDIUM."""
    e = DetectionEngine(cfg())
    steady(e, 10)
    # history: 1 port per window, std floor 1 -> z = ports - 1; ratio = z / 3
    odd = [flow(T0 + 600 + i * 2, dport=80 if i >= ports else 1000 + i) for i in range(30)]
    (det,) = run(e, odd, until=T0 + 661.5)
    assert (det["type"], det["severity"], det["alert"]) == ("unknown", severity, alert)


def test_cooldown_one_alert_per_attack():
    """A scan over several windows raises one alert; the detections are all kept."""
    e = DetectionEngine(cfg())
    dets = [d for k in range(4) for d in scan_at(e, T0 + 10 * k, 160)]
    assert len(dets) == 4
    assert [d["alert"] for d in dets] == [True, False, False, False]


def test_escalation_inside_cooldown_alerts_again():
    e = DetectionEngine(cfg())
    first = scan_at(e, T0, 160)  # MEDIUM
    worse = scan_at(e, T0 + 10, 400)  # HIGH
    assert first[0]["alert"] and worse[0]["alert"]


def test_alert_again_after_cooldown():
    e = DetectionEngine(cfg(**{"alerts.cooldown_s": 30}))
    assert scan_at(e, T0, 160)[0]["alert"]
    assert not scan_at(e, T0 + 20, 160)[0]["alert"]
    assert scan_at(e, T0 + 40, 160)[0]["alert"]


def test_detection_escalating_to_alert_level_gets_alert_flag():
    """LOW early, then MEDIUM in the same window: the re-sent detection carries alert=true."""
    e = DetectionEngine(cfg())
    low = run(e, [flow(T0 + 1, dport=p) for p in range(1, 121)], until=T0 + 2)
    medium = run(e, [flow(T0 + 2, dport=p) for p in range(121, 161)], until=T0 + 3)
    assert (low[0]["alert"], medium[0]["alert"]) == (False, True)
    assert low[0]["detection_id"] == medium[0]["detection_id"]


# ---- labels (DQ-07) ----


def test_labels_are_never_read():
    """DQ-07: the same flows without labels give exactly the same detections."""

    def detections(with_labels):
        e = DetectionEngine(cfg())
        out = []
        for k in range(3):
            fl = [flow(T0 + 10 * k + 1, dport=p, label="port_scan") for p in range(1, 161)]
            if not with_labels:
                for f in fl:
                    f["label"] = None
            out += run(e, fl, until=T0 + 10 * k + 12)
        return [(d["detection_id"], d["severity"], d["alert"]) for d in out]

    assert detections(True) == detections(False)
