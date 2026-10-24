"""Flow-file importer (owner: Member 1).

Reads a labelled network-flow CSV, normalises each row into a flow.v1 message,
validates it, and publishes it to flows.raw (keyed by src_ip). It is the first
component to touch the data, so it creates the trace_id (F15) and sets
ingested_at (NFR02). Malformed rows are rejected with their reason, sent to the
dead-letter topic, and never published (F01, SEC-02); a summary is printed at
the end.

Run locally (broker must be up):
    FLOW_FILE=data/flows/sample.csv BROKER_BOOTSTRAP=localhost:19092 \
        python services/importer/importer.py
"""

from __future__ import annotations

import csv
import os
import time
import uuid
from collections import defaultdict

from netguard_common import get_logger, setup_logging, trace_context
from netguard_common.messages import SchemaError, flow_id_for, validate_flow

log = get_logger("importer")

VALID_PROTOCOLS = {"TCP", "UDP", "ICMP", "OTHER"}
PROTOCOL_BY_NUMBER = {"1": "ICMP", "6": "TCP", "17": "UDP"}
VALID_LABELS = {"normal", "port_scan", "dos", "brute_force", "abnormal_traffic"}
REQUIRED_COLUMNS = (
    "ts_start",
    "duration_ms",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "packets",
    "bytes",
)


def _protocol(raw: str) -> str:
    p = (raw or "").strip().upper()
    if p in VALID_PROTOCOLS:
        return p
    return PROTOCOL_BY_NUMBER.get(p, "OTHER")


def _ts_start(raw: str) -> float:
    raw = (raw or "").strip()
    try:
        return float(raw)  # epoch seconds
    except ValueError:
        from datetime import datetime

        return datetime.fromisoformat(raw.replace(" ", "T")).timestamp()


def _label(raw: str) -> str | None:
    v = (raw or "").strip().lower()
    if v in ("", "none", "null"):
        return None
    if v == "benign":
        return "normal"
    if v in VALID_LABELS:
        return v
    raise ValueError(f"unknown label '{raw}'")


def _tcp_flags(raw: str) -> str | None:
    return (raw or "").strip().upper() or None


def normalise_row(row: dict[str, str]) -> dict:
    """Pure: one CSV row -> the flow.v1 payload fields. Raises ValueError on a bad row."""
    missing = [c for c in REQUIRED_COLUMNS if not (row.get(c) or "").strip()]
    if missing:
        raise ValueError(f"missing/empty columns: {', '.join(missing)}")
    return {
        "ts_start": _ts_start(row["ts_start"]),
        "duration_ms": float(row["duration_ms"]),
        "src_ip": row["src_ip"].strip(),
        "dst_ip": row["dst_ip"].strip(),
        "src_port": int(row["src_port"]),
        "dst_port": int(row["dst_port"]),
        "protocol": _protocol(row["protocol"]),
        "packets": int(row["packets"]),
        "bytes": int(row["bytes"]),
        "tcp_flags": _tcp_flags(row.get("tcp_flags", "")),
        "label": _label(row.get("label", "")),
    }


def build_flow(row: dict, source_file: str, index: int, ingested_at: float, trace_id: str) -> dict:
    """Full flow.v1 message for one row. Does not validate (caller does, to handle rejects)."""
    flow = normalise_row(row)
    flow.update(
        schema_version=1,
        flow_id=flow_id_for(source_file, index),
        trace_id=trace_id,
        ingested_at=ingested_at,
        source="flowfile",
    )
    return flow


def main() -> None:
    from netguard_common import topics
    from netguard_common.broker import encode, ensure_topics, make_producer

    setup_logging("importer")
    flow_file = os.getenv("FLOW_FILE", "/app/data/flows/sample.csv")
    source_name = os.path.basename(flow_file)

    if not os.path.exists(flow_file):
        log.error("flow file not found", extra={"flow_file": flow_file})
        raise SystemExit(1)

    ensure_topics()
    producer = make_producer()
    log.info("importer started", extra={"flow_file": flow_file})

    accepted = 0
    rejected = 0
    reasons: dict[str, int] = defaultdict(int)

    try:
        with open(flow_file, newline="") as f:
            for i, row in enumerate(csv.DictReader(f)):
                trace_id = uuid.uuid4().hex
                ingested_at = time.time()
                try:
                    flow = build_flow(row, source_name, i, ingested_at, trace_id)
                    validate_flow(flow)
                except (ValueError, SchemaError) as e:
                    rejected += 1
                    reasons[str(e)[:80]] += 1
                    with trace_context(trace_id):
                        log.error("flow rejected", extra={"row": i, "reason": str(e)})
                    producer.produce(topics.DEAD_LETTER, value=encode({"row": i, "reason": str(e), "raw": row}))
                    continue
                with trace_context(trace_id):
                    producer.produce(topics.FLOWS_RAW, key=flow["src_ip"], value=encode(flow))
                accepted += 1
                if (accepted + rejected) % 1000 == 0:
                    producer.poll(0)
    finally:
        producer.flush(10)

    log.info("importer finished", extra={"accepted": accepted, "rejected": rejected, "reasons": dict(reasons)})
    print(f"[importer] accepted={accepted} rejected={rejected} reasons={dict(reasons)}")


if __name__ == "__main__":
    main()
