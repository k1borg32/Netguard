"""Stream processor + detection engine - SKELETON (owner: Member 2).

Scalable: run N instances (`docker compose up --scale processor=3`). They share
consumer group "processor"; Kafka assigns partitions, and because flows are
keyed by src_ip, each source's windows live in exactly one instance.

What's here is a placeholder rule (port scan, 10 s tumbling window) that proves
the pipeline end to end. Member 2 replaces `WindowState`/`rules()` with the real
1/10/60 s windows, four rules and the statistical method.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field

import yaml

from netguard_common import detection_id, get_logger, setup_logging, trace_context

log = get_logger("processor")


@dataclass
class SourceWindow:
    dst_ports: set[int] = field(default_factory=set)
    dst_ips: set[str] = field(default_factory=set)
    flows: int = 0
    first_ingested_at: float = float("inf")
    trace_ids: list[str] = field(default_factory=list)


class WindowState:
    """Tumbling windows keyed by (src_ip, window_start). Pure logic, unit-testable without a broker."""

    def __init__(self, size_s: int, grace_s: float = 1.0):
        self.size_s = size_s
        self.grace_s = grace_s
        self.windows: dict[tuple[str, float], SourceWindow] = defaultdict(SourceWindow)

    def window_start(self, ts: float) -> float:
        return ts - (ts % self.size_s)

    def add(self, flow: dict) -> None:
        w = self.windows[(flow["src_ip"], self.window_start(flow["ts_start"]))]
        w.dst_ports.add(flow["dst_port"])
        w.dst_ips.add(flow["dst_ip"])
        w.flows += 1
        w.first_ingested_at = min(w.first_ingested_at, flow["ingested_at"])
        if len(w.trace_ids) < 20:
            w.trace_ids.append(flow["trace_id"])

    def pop_closed(self, now: float) -> list[tuple[str, float, SourceWindow]]:
        closed = [k for k in self.windows if k[1] + self.size_s + self.grace_s <= now]
        return [(src, start, self.windows.pop((src, start))) for src, start in closed]


def port_scan_rule(src: str, start: float, w: SourceWindow, size_s: int, threshold: int, now: float) -> dict | None:
    n = len(w.dst_ports)
    if n < threshold:
        return None
    ratio = n / threshold
    severity = "CRITICAL" if ratio >= 5 else "HIGH" if ratio >= 3 else "MEDIUM" if ratio >= 1.5 else "LOW"
    dst = next(iter(w.dst_ips)) if len(w.dst_ips) == 1 else None
    return {
        "schema_version": 1,
        "detection_id": detection_id("port_scan", "rule", src, dst, start, size_s),
        "trace_ids": w.trace_ids,
        "created_at": now,
        "first_ingested_at": w.first_ingested_at,
        "type": "port_scan",
        "method": "rule",
        "severity": severity,
        "confidence": round(min(1.0, 0.5 + 0.1 * ratio), 3),
        "src_ip": src,
        "dst_ip": dst,
        "window": {"size_s": size_s, "start": start, "end": start + size_s},
        "features": {"unique_dst_ports": n, "unique_dst_ips": len(w.dst_ips), "flows": w.flows, "threshold": threshold},
        "explanation": f"{src} contacted {n} distinct destination ports in {size_s}s (threshold {threshold}).",
    }


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    from netguard_common import topics
    from netguard_common.broker import encode, ensure_topics, make_consumer, make_producer, poll_batch

    setup_logging("processor")
    cfg = load_config(os.getenv("DETECTION_CONFIG", "/app/config/detection.yaml"))
    rule = cfg["rules"]["port_scan"]
    state = WindowState(size_s=rule["window_s"])

    ensure_topics()
    consumer = make_consumer("processor", [topics.FLOWS_RAW])
    producer = make_producer()
    log.info("processor started", extra={"instance": os.getenv("HOSTNAME")})

    try:
        while True:
            got = 0
            for _, flow in poll_batch(consumer):
                state.add(flow)
                got += 1
            now = time.time()
            for src, start, w in state.pop_closed(now):
                det = port_scan_rule(src, start, w, state.size_s, rule["unique_dst_ports_threshold"], now)
                if det:
                    with trace_context(w.trace_ids[0]):
                        producer.produce(topics.DETECTIONS, key=det["detection_id"], value=encode(det))
                        log.info(
                            "detection",
                            extra={
                                "detection_id": det["detection_id"],
                                "type": det["type"],
                                "latency_s": round(now - det["first_ingested_at"], 3),
                            },
                        )
            producer.poll(0)
            if got:
                # KNOWN LIMITATION (doc it in test report): offsets are committed before open windows
                # close, so a crash loses at most one window of in-memory state. Fix = replay from
                # (window_start) offsets or a state store. Discuss with Member 2 in week 2.
                consumer.commit(asynchronous=True)
    finally:
        producer.flush(5)
        consumer.close()


if __name__ == "__main__":
    main()
