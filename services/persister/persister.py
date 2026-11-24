"""Persister (owner: Member 3).

Consumes flows.raw and detections, writes to PostgreSQL/TimescaleDB in batches.
Batching is mandatory for NFR01: one INSERT per flow will not survive 5,000 flows/s.
Detections upsert on the deterministic detection_id, so re-delivered messages
never create duplicates. The detection engine sends a detection again when it
escalates inside its window; the stored row is only updated when the new
severity is higher, so redelivery of an older message never downgrades it.
Detections with `alert: true` (the engine's alert policy, detection.yaml
`alerts`) also get an alert row; at most one per detection (F17).
"""

from __future__ import annotations

import json
import os
import time
import uuid

import psycopg
from confluent_kafka import Consumer

from netguard_common import get_logger, setup_logging, topics, trace_context
from netguard_common.messages import NETGUARD_NS

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

_FLOW_COLUMNS = ", ".join(FLOW_COLS)
_FLOW_EPOCH_COLUMNS = {"ingested_at", "ts_start"}
_FLOW_BATCH_COLUMNS = ", ".join(
    f"NULL::double precision AS {column}" if column in _FLOW_EPOCH_COLUMNS else column for column in FLOW_COLS
)
_FLOW_INSERT_COLUMNS = ", ".join(
    f"to_timestamp({column})" if column in _FLOW_EPOCH_COLUMNS else column for column in FLOW_COLS
)
FLOW_BATCH_SQL = (
    "CREATE TEMP TABLE flow_batch ON COMMIT DELETE ROWS AS "
    f"SELECT {_FLOW_BATCH_COLUMNS}, NULL::integer AS batch_order FROM network_flows WITH NO DATA"
)
FLOW_COPY_SQL = f"COPY flow_batch ({_FLOW_COLUMNS}, batch_order) FROM STDIN"
FLOW_INSERT_SQL = (
    f"INSERT INTO network_flows ({_FLOW_COLUMNS}) "
    f"SELECT {_FLOW_INSERT_COLUMNS} FROM flow_batch ORDER BY batch_order ON CONFLICT DO NOTHING"
)


def write_flows(cur: psycopg.Cursor, flows: list[dict]) -> None:
    # Keep the first occurrence of a key, including duplicates within this batch.
    with cur.copy(FLOW_COPY_SQL) as copy:
        for order, flow in enumerate(flows):
            copy.write_row(tuple(flow.get(column) for column in FLOW_COLS) + (order,))
    cur.execute(FLOW_INSERT_SQL)


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


def alert_row(d: dict) -> tuple:
    """Deterministic alert_id, so a redelivered detection maps to the same alert."""
    return (str(uuid.uuid5(NETGUARD_NS, f"alert|{d['detection_id']}")), d["detection_id"], d["created_at"])


def log_written_batch(flows: list[dict], detections: list[dict], alert_count: int) -> None:
    trace_ids = []
    for flow in flows:
        if flow.get("trace_id"):
            trace_ids.append(flow["trace_id"])
    for detection in detections:
        trace_ids.extend(detection.get("trace_ids", []))
    trace_ids = list(dict.fromkeys(trace_ids))

    # A batch can contain unrelated events; keep every ID for trace lookups.
    representative_trace_id = None
    if trace_ids:
        representative_trace_id = trace_ids[0]
    with trace_context(representative_trace_id):
        log.info(
            "batch written",
            extra={
                "flows": len(flows),
                "detections": len(detections),
                "alerts": alert_count,
                "trace_ids": trace_ids,
            },
        )


SEVERITY_ORDER = "ARRAY['LOW','MEDIUM','HIGH','CRITICAL']"
DET_SQL = (
    "INSERT INTO detections (detection_id, created_at, first_ingested_at, last_ingested_at, type, method, "
    "severity, confidence, src_ip, dst_ip, window_size_s, window_start, window_end, features, explanation, "
    "trace_ids) VALUES (%s, to_timestamp(%s), to_timestamp(%s), to_timestamp(%s), %s, %s, %s, %s, %s, %s, "
    "%s, to_timestamp(%s), to_timestamp(%s), %s, %s, %s) "
    # escalation: keep created_at and last_ingested_at, the pair the latency of the first detection is measured
    # from (NFR02), and take the stronger evidence
    "ON CONFLICT (detection_id) DO UPDATE SET severity = EXCLUDED.severity, confidence = EXCLUDED.confidence, "
    "features = EXCLUDED.features, explanation = EXCLUDED.explanation, trace_ids = EXCLUDED.trace_ids "
    f"WHERE array_position({SEVERITY_ORDER}, EXCLUDED.severity) > array_position({SEVERITY_ORDER}, detections.severity)"
)
ALERT_SQL = (
    "INSERT INTO alerts (alert_id, detection_id, status, created_at) VALUES (%s, %s, 'NEW', to_timestamp(%s)) "
    "ON CONFLICT (detection_id) DO NOTHING"
)


def consume_batches(conn: psycopg.Connection, consumer: Consumer) -> None:
    from netguard_common.broker import poll_batch

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
                write_flows(cur, flows)
            if dets:
                cur.executemany(DET_SQL, [detection_row(d) for d in dets])
            alerts = [alert_row(d) for d in dets if d.get("alert")]
            if alerts:  # after the detections: alerts.detection_id references them
                cur.executemany(ALERT_SQL, alerts)
        conn.commit()
        consumer.commit(asynchronous=False)  # only after DB commit -> at-least-once
        log_written_batch(flows, dets, len(alerts))


def main() -> None:
    from netguard_common.broker import ensure_topics, make_consumer

    setup_logging("persister")
    ensure_topics()
    retry_delay = 1

    while True:
        conn = None
        consumer = None
        try:
            conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=False, connect_timeout=5)
            # Temporary tables belong to the connection and must be recreated.
            conn.execute(FLOW_BATCH_SQL)
            conn.commit()
            consumer = make_consumer("persister", [topics.FLOWS_RAW, topics.DETECTIONS])
            retry_delay = 1
            log.info("persister connected")
            consume_batches(conn, consumer)
        except (psycopg.OperationalError, psycopg.InterfaceError) as error:
            log.warning(
                "database unavailable; reconnecting",
                extra={"error_type": type(error).__name__, "retry_delay_s": retry_delay},
            )
        finally:
            try:
                if consumer is not None:
                    # Auto-commit is disabled: unfinished batches will be replayed.
                    consumer.close()
            finally:
                if conn is not None:
                    conn.close()

        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 30)


if __name__ == "__main__":
    main()
