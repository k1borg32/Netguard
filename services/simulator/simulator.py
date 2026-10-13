"""Traffic simulator - SKELETON (owner: Member 1; load mode owned by Member 5).

Generates synthetic flows (no real packets, no real network) and publishes
them to flows.raw. Every flow carries a ground-truth `label` for detection metrics.

Implemented now: normal traffic + port_scan (enough for the week-3 thin pipeline).
TODO week 4: dos, brute_force, abnormal_pattern scenarios.

Env:
  SIM_RATE        flows per second (default 200; perf test uses 5000+)
  SIM_DURATION_S  stop after N seconds (0 = forever)
  SIM_SCENARIOS   comma list, e.g. "normal,port_scan"
"""

from __future__ import annotations

import os
import random
import time
import uuid

from netguard_common import get_logger, new_trace_id, setup_logging, topics, validate_flow

log = get_logger("simulator")

CLIENTS = [f"10.0.{i // 250}.{i % 250 + 1}" for i in range(200)]
SERVERS = [f"10.1.0.{i}" for i in range(1, 21)]
COMMON_PORTS = [80, 443, 53, 22, 3306, 5432, 8080]


def normal_flow(now: float) -> dict:
    return _flow(
        now,
        random.choice(CLIENTS),
        random.choice(SERVERS),
        random.choice(COMMON_PORTS),
        packets=random.randint(4, 60),
        flags="SA",
        label="normal",
    )


def port_scan_flow(now: float, attacker: str, target: str) -> dict:
    return _flow(now, attacker, target, random.randint(1, 65535), packets=1, flags="S", label="port_scan")


def _flow(now: float, src: str, dst: str, dport: int, packets: int, flags: str, label: str) -> dict:
    return {
        "schema_version": 1,
        "flow_id": str(uuid.uuid4()),
        "trace_id": new_trace_id(),
        "ingested_at": time.time(),
        "ts_start": now,
        "duration_ms": round(random.uniform(0.1, 500), 2),
        "src_ip": src,
        "dst_ip": dst,
        "src_port": random.randint(1024, 65535),
        "dst_port": dport,
        "protocol": "TCP",
        "packets": packets,
        "bytes": packets * random.randint(60, 1400),
        "tcp_flags": flags,
        "source": "simulator",
        "label": label,
    }


def generate(scenarios: list[str], n: int, now: float) -> list[dict]:
    out = []
    for _ in range(n):
        if "port_scan" in scenarios and random.random() < 0.05:
            out.append(port_scan_flow(now, "10.66.6.6", SERVERS[0]))
        else:
            out.append(normal_flow(now))
    return out


def main() -> None:
    from netguard_common.broker import encode, ensure_topics, make_producer

    setup_logging("simulator")
    rate = int(os.getenv("SIM_RATE", "200"))
    duration = float(os.getenv("SIM_DURATION_S", "0"))
    scenarios = os.getenv("SIM_SCENARIOS", "normal,port_scan").split(",")
    ensure_topics()
    producer = make_producer()
    log.info("simulator started", extra={"rate": rate, "scenarios": scenarios})

    start = time.time()
    sent = 0
    tick = 0.1  # send in 100 ms slices for smooth rate
    while duration == 0 or time.time() - start < duration:
        slice_start = time.time()
        for f in generate(scenarios, max(1, int(rate * tick)), slice_start):
            validate_flow(f) if sent % 1000 == 0 else None  # spot-check, full validation is too slow at 5k/s
            producer.produce(topics.FLOWS_RAW, key=f["src_ip"], value=encode(f))
            sent += 1
        producer.poll(0)
        time.sleep(max(0.0, tick - (time.time() - slice_start)))
        if sent % (rate * 10) < rate * tick:
            log.info("progress", extra={"sent": sent, "elapsed_s": round(time.time() - start, 1)})
    producer.flush(10)
    log.info("simulator finished", extra={"sent": sent})


if __name__ == "__main__":
    main()
