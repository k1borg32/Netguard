"""Flow importer (owner: Member 1).

Reads network-flow data and publishes normalised flow.v1 messages to flows.raw
(keyed by src_ip). Input format is picked by file extension:
  * .csv          -> labelled flow records   (source="flowfile"), streamed row by row
  * .pcap / .cap  -> classic Ethernet capture; packets grouped into flows (source="pcap")
Anything else (including .pcapng) is rejected with a clear error.

First component to touch the data, so it creates trace_id (F15) and sets
ingested_at (NFR02). Malformed records are rejected with their reason, sent to
the dead-letter topic, and never published (F01, SEC-02). Whatever happens,
including an unreadable or truncated input file, a summary is printed at the
end; the exit code is 1 only if the file as a whole could not be imported.

Run locally (broker must be up):
    FLOW_FILE=data/flows/sample.csv  python services/importer/importer.py
    FLOW_FILE=data/pcap/sample.pcap  python services/importer/importer.py
"""

from __future__ import annotations

import csv
import json
import os
import time
from collections import defaultdict
from importlib import resources

from netguard_common import get_logger, new_trace_id, setup_logging, trace_context
from netguard_common.messages import SchemaError, flow_id_for, validate_flow

log = get_logger("importer")


class InputError(Exception):
    """The input file as a whole cannot be imported (wrong type, unreadable, ...)."""


def _schema_labels() -> set[str]:
    """Allowed labels come from flow.v1.json so the importer can never drift from the schema."""
    raw = resources.files("netguard_common").joinpath("schemas/flow.v1.json").read_text()
    return {label for label in json.loads(raw)["properties"]["label"]["enum"] if label}


VALID_PROTOCOLS = {"TCP", "UDP", "ICMP", "OTHER"}
PROTOCOL_BY_NUMBER = {"1": "ICMP", "6": "TCP", "17": "UDP"}
VALID_LABELS = _schema_labels()
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
CSV_EXTENSIONS = (".csv",)
PCAP_EXTENSIONS = (".pcap", ".cap")
# The PCAP path keeps all flows in memory; big captures must be converted to flow CSV first.
MAX_PCAP_MB = int(os.getenv("MAX_PCAP_MB", "200"))


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


def _csv_records(flow_file: str):
    """Stream CSV rows. A file that is not a readable CSV with the needed header is an InputError."""
    try:
        with open(flow_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise InputError(f"CSV header is missing columns: {', '.join(missing)}")
            for row in reader:
                yield "row", row, "flowfile"
    except (UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"not a readable CSV text file: {e}") from e


def _pcap_records(flow_file: str, warnings: list[str]):
    from pcap_reader import PcapFormatError, check_pcap, extract_flows, iter_packets

    size_mb = os.path.getsize(flow_file) / 1_000_000
    if size_mb > MAX_PCAP_MB:
        raise InputError(
            f"capture is {size_mb:.0f} MB (limit {MAX_PCAP_MB} MB): the PCAP path keeps all flows "
            "in memory, convert it to a flow CSV first"
        )
    try:
        records, truncated = check_pcap(flow_file)
    except PcapFormatError as e:
        raise InputError(str(e)) from e
    if truncated:
        warnings.append(f"capture is truncated: only the first {records} complete packet records were imported")
    for fields in extract_flows(iter_packets(flow_file, max_records=records)):
        yield "fields", fields, "pcap"


def _raw_records(flow_file: str, warnings: list[str]):
    """Yield (kind, record, source) for each input item.

    kind 'row'    -> record is a raw CSV row, normalised later (may be rejected).
    kind 'fields' -> record is an already-structured PCAP flow.
    Raises InputError when the file as a whole cannot be imported.
    """
    ext = os.path.splitext(flow_file)[1].lower()
    if ext == ".pcapng":
        raise InputError("pcapng is not supported, only classic .pcap (convert: editcap -F pcap in.pcapng out.pcap)")
    if ext in PCAP_EXTENSIONS:
        yield from _pcap_records(flow_file, warnings)
    elif ext in CSV_EXTENSIONS:
        yield from _csv_records(flow_file)
    else:
        raise InputError(f"unsupported file type '{ext or '(none)'}': use .csv or .pcap")


def main() -> None:
    from netguard_common import topics
    from netguard_common.broker import encode, ensure_topics, make_producer

    setup_logging("importer")
    flow_file = os.getenv("FLOW_FILE", "/app/data/flows/sample.csv")
    source_name = os.path.basename(flow_file)

    accepted = rejected = 0
    reasons: dict[str, int] = defaultdict(int)
    warnings: list[str] = []
    fatal: str | None = None
    producer = None

    try:
        if not os.path.exists(flow_file):
            raise InputError(f"file not found: {flow_file}")
        ensure_topics()
        producer = make_producer()
        log.info("importer started", extra={"flow_file": flow_file})

        for index, (kind, rec, source) in enumerate(_raw_records(flow_file, warnings)):
            trace_id = new_trace_id()
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
    except InputError as e:
        fatal = str(e)
    except Exception as e:  # last resort: the summary must always be printed
        fatal = f"{type(e).__name__}: {e}"
    finally:
        if producer is not None:
            producer.flush(10)

    if fatal is None and accepted + rejected == 0:
        warnings.append("input contained no records")

    extra = {
        "accepted": accepted,
        "rejected": rejected,
        "reasons": dict(reasons),
        "warnings": warnings,
        "error": fatal,
    }
    if fatal:
        log.error("importer failed", extra=extra)
    else:
        log.info("importer finished", extra=extra)
    print(
        f"[importer] accepted={accepted} rejected={rejected} reasons={dict(reasons)} warnings={warnings} error={fatal}"
    )
    raise SystemExit(1 if fatal else 0)


if __name__ == "__main__":
    main()
