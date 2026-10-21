"""Persister - SKELETON (owner: Member 3).

Consumes flows.raw and detections, writes to PostgreSQL/TimescaleDB in batches.
Batching is mandatory for NFR01: one INSERT per flow will not survive 5,000 flows/s.
Detections use ON CONFLICT DO NOTHING on the deterministic detection_id, so
re-delivered messages never create duplicate alerts.
"""

from __future__ import annotations

import json
import os
import time

import psycopg

from netguard_common import get_logger, setup_logging, topics

log = get_logger("persister")

FLOW_COLS = (
    "flow_id",
    "trace_id",
    "ingested_at",
    "ts_start",
    "duration_ms",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "packets",
    "bytes",
    "tcp_flags",
    "source",
    "label",
)

_FLOW_PLACEHOLDERS = ["to_timestamp(%s)" if c in ("ingested_at", "ts_start") else "%s" for c in FLOW_COLS]
FLOW_INSERT_SQL = (
    f"INSERT INTO network_flows ({','.join(FLOW_COLS)}) VALUES ({','.join(_FLOW_PLACEHOLDERS)}) ON CONFLICT DO NOTHING"
)


def flow_row(f: dict) -> tuple:
    return tuple(f.get(c) for c in FLOW_COLS)


def detection_row(d: dict) -> tuple:
    return (
        d["detection_id"],
        d["created_at"],
        d["first_ingested_at"],
        d["last_ingested_at"],
        d["type"],
        d["method"],
        d["severity"],
        d["confidence"],
        d["src_ip"],
        d["dst_ip"],
        d["window"]["size_s"],
        d["window"]["start"],
        d["window"]["end"],
        json.dumps(d["features"]),
        d["explanation"],
        d["trace_ids"],
    )


def main() -> None:
    from netguard_common.broker import ensure_topics, make_consumer, poll_batch

    setup_logging("persister")
    ensure_topics()
    consumer = make_consumer("persister", [topics.FLOWS_RAW, topics.DETECTIONS])
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=False)
    log.info("persister started")

    det_sql = (
        "INSERT INTO detections (detection_id, created_at, first_ingested_at, last_ingested_at, type, method, "
        "severity, confidence, src_ip, dst_ip, window_size_s, window_start, window_end, features, explanation, "
        "trace_ids) VALUES (%s, to_timestamp(%s), to_timestamp(%s), to_timestamp(%s), %s, %s, %s, %s, %s, %s, "
        "%s, to_timestamp(%s), to_timestamp(%s), %s, %s, %s) ON CONFLICT (detection_id) DO NOTHING"
    )

    while True:
        flows, dets = [], []
        deadline = time.time() + 0.5
        while time.time() < deadline and len(flows) < 5000:
            for m, msg in poll_batch(consumer, max_messages=1000, timeout=0.1):
                (dets if m.topic() == topics.DETECTIONS else flows).append(msg)
        if not flows and not dets:
            continue
        with conn.cursor() as cur:
            if flows:
                cur.executemany(FLOW_INSERT_SQL, [flow_row(f) for f in flows])
            if dets:
                cur.executemany(det_sql, [detection_row(d) for d in dets])
        conn.commit()
        consumer.commit(asynchronous=False)  # only after DB commit -> at-least-once
        log.info("batch written", extra={"flows": len(flows), "detections": len(dets)})


if __name__ == "__main__":
    main()
