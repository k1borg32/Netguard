"""Flow importer (owner: Member 1).

Reads network-flow data and publishes normalised flow.v1 messages to flows.raw
(keyed by src_ip). Input format is picked by file extension:
  * .csv          -> labelled flow records   (source="flowfile")
  * .pcap / .cap  -> raw capture; packets grouped into flows (source="pcap")

First component to touch the data, so it creates trace_id (F15) and sets
ingested_at (NFR02). Malformed records are rejected with their reason, sent to
the dead-letter topic, and never published (F01, SEC-02); a summary prints at
the end.

Run locally (broker must be up):
    FLOW_FILE=data/flows/sample.csv  python services/importer/importer.py
    FLOW_FILE=data/pcap/sample.pcap  python services/importer/importer.py
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
PCAP_EXTENSIONS = (".pcap", ".cap", ".pcapng")


def _protocol(raw: str) -> str:
    p = (raw or "").strip().upper()
    if p in VALID_PROTOCOLS:
        return p
    return PROTOCOL_BY_NUMBER.get(p, "OTHER")


def _ts_start(raw: str) -> float:
    raw = (raw or "").strip()
    try:
        return float(raw)
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
    """Pure: one CSV row -> flow.v1 field dict. Raises ValueError on a bad row."""
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


def finalise_flow(fields, source_file, index, ingested_at, trace_id, source) -> dict:
    """Add the flow.v1 envelope (schema_version, flow_id, trace_id, ingested_at, source)."""
    return {
        **fields,
        "schema_version": 1,
        "flow_id": flow_id_for(source_file, index),
        "trace_id": trace_id,
        "ingested_at": ingested_at,
        "source": source,
    }


def build_flow(row, source_file, index, ingested_at, trace_id) -> dict:
    """CSV row -> full flow.v1 message (source='flowfile'). Does not validate."""
    return finalise_flow(normalise_row(row), source_file, index, ingested_at, trace_id, "flowfile")


def _raw_records(flow_file: str):
    """Yield (kind, record, source) for each input item.

    kind 'row'    -> record is a raw CSV row, normalised later (may be rejected).
    kind 'fields' -> record is an already-structured PCAP flow.
    """
    ext = os.path.splitext(flow_file)[1].lower()
    if ext in PCAP_EXTENSIONS:
        from pcap_reader import extract_flows, iter_packets

        for fields in extract_flows(iter_packets(flow_file)):
            yield "fields", fields, "pcap"
    else:
        with open(flow_file, newline="") as f:
            for row in csv.DictReader(f):
                yield "row", row, "flowfile"


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

    accepted = rejected = 0
    reasons: dict[str, int] = defaultdict(int)

    for index, (kind, rec, source) in enumerate(_raw_records(flow_file)):
        trace_id = uuid.uuid4().hex
        ingested_at = time.time()
        try:
            fields = normalise_row(rec) if kind == "row" else rec
            flow = finalise_flow(fields, source_name, index, ingested_at, trace_id, source)
            validate_flow(flow)
        except (ValueError, SchemaError) as e:
            rejected += 1
            reasons[str(e)[:80]] += 1
            with trace_context(trace_id):
                log.error("flow rejected", extra={"row": index, "reason": str(e)})
            producer.produce(topics.DEAD_LETTER, value=encode({"row": index, "reason": str(e)}))
            continue
        with trace_context(trace_id):
            producer.produce(topics.FLOWS_RAW, key=flow["src_ip"], value=encode(flow))
        accepted += 1
        if (index + 1) % 1000 == 0:
            producer.poll(0)

    producer.flush(10)
    log.info("importer finished", extra={"accepted": accepted, "rejected": rejected, "reasons": dict(reasons)})
    print(f"[importer] accepted={accepted} rejected={rejected} reasons={dict(reasons)}")


if __name__ == "__main__":
    main()
