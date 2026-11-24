"""CIC-IDS2017 labelled flows -> NetGuard flow CSV (owner: Member 1).

Input: one CSV from the "TrafficLabelling" folder of CIC-IDS2017 (it has Source IP,
Destination IP and Timestamp; the MachineLearningCVE files do not).
Output: a flow CSV that the importer reads as it is.

Usage:
    python3 services/importer/convert_cic.py data/raw/<file>.csv data/flows/<name>.csv

Only the classes our detectors can see are kept by default (BENIGN, PortScan, DoS/DDoS,
FTP/SSH-Patator). Other attack classes are skipped and counted; --include-other maps them
to brute_force / suspicious_pattern instead.

Standard library only, so it runs on the host without Docker.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter
from datetime import UTC, datetime

LABEL_MAP = {
    "benign": "normal",
    "portscan": "port_scan",
    "ddos": "dos",
    "dos hulk": "dos",
    "dos goldeneye": "dos",
    "dos slowloris": "dos",
    "dos slowhttptest": "dos",
    "ftp-patator": "brute_force",
    "ssh-patator": "brute_force",
}
EXTRA_LABEL_MAP = {
    "web attack brute force": "brute_force",
    "web attack xss": "suspicious_pattern",
    "web attack sql injection": "suspicious_pattern",
    "bot": "suspicious_pattern",
    "infiltration": "suspicious_pattern",
    "heartbleed": "suspicious_pattern",
}

OUT_COLUMNS = (
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
    "label",
)
REQUIRED = (
    "source ip",
    "source port",
    "destination ip",
    "destination port",
    "protocol",
    "timestamp",
    "flow duration",
    "total fwd packets",
    "total backward packets",
    "total length of fwd packets",
    "total length of bwd packets",
    "label",
)
# flag letter (flow.v1 pattern ^[FSRPAUEC]*$) -> CIC column holding its packet count
FLAG_COLUMNS = (
    ("F", "fin flag count"),
    ("S", "syn flag count"),
    ("R", "rst flag count"),
    ("P", "psh flag count"),
    ("A", "ack flag count"),
    ("U", "urg flag count"),
    ("E", "ece flag count"),
    ("C", "cwe flag count"),
)
PROTOCOLS = {6: "TCP", 17: "UDP", 1: "ICMP"}
ISO_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f")
DMY_FORMATS = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M")


def norm_label(raw: str) -> str:
    """'Web Attack <bad byte> Brute Force' -> 'web attack brute force'."""
    return " ".join(re.sub(r"[^a-z0-9-]+", " ", (raw or "").lower()).split())


def parse_timestamp(raw: str, pm_before: int = 8) -> tuple[float, bool]:
    """Return (epoch seconds, has_seconds).

    CIC writes day/month/year with a 12-hour clock but no AM/PM, so hours before
    `pm_before` are taken as afternoon (the capture ran from morning to 5 pm).
    Use pm_before=0 if your file already has a 24-hour clock. Times are treated as UTC;
    only the differences between flows matter.
    """
    text = (raw or "").strip()
    for fmt in ISO_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return dt.replace(tzinfo=UTC).timestamp(), True
    for fmt in DMY_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if dt.hour < pm_before:
            dt = dt.replace(hour=dt.hour + 12)
        return dt.replace(tzinfo=UTC).timestamp(), fmt.endswith("%S")
    raise ValueError(f"bad timestamp '{raw}'")


def _num(text: str) -> float:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


def _index(header: list[str]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, name in enumerate(header):
        idx.setdefault(name.strip().lower(), i)
    return idx


def _flags(line: list[str], idx: dict[str, int]) -> str:
    out = ""
    for letter, col in FLAG_COLUMNS:
        j = idx.get(col)
        if j is not None and _num(line[j]) > 0:
            out += letter
    return out


# CICFlowMeter calls the sender of the first packet of a flow "source". A reply of the victim to the attacker can be
# recorded that way (server -> client). In our manifests the attacker is the source, so these attack flows are turned
# around: addresses and ports are swapped.
VICTIM_NET = "192.168.10."
ATTACKER_NAT = "172.16.0.1"


def convert(
    src: str,
    dst: str,
    *,
    include_other: bool = False,
    from_time: str | None = None,
    to_time: str | None = None,
    pm_before: int = 8,
    spread_minutes: bool = False,
    limit: int | None = None,
) -> dict:
    """Convert one CIC-IDS2017 file. Returns statistics. Raises ValueError for a wrong file."""
    mapping = {**LABEL_MAP, **(EXTRA_LABEL_MAP if include_other else {})}
    skipped: Counter = Counter()
    rows: list[list] = []  # [ts, has_seconds, duration_ms, src, dst, sport, dport, proto, pkts, bytes, flags, label]
    read = 0
    turned_around = 0

    with open(src, newline="", encoding="latin-1") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            raise ValueError("the file is empty")
        idx = _index(header)
        missing = [c for c in REQUIRED if c not in idx]
        if missing:
            shown = ", ".join(h.strip() for h in header[:12])
            raise ValueError(
                f"missing columns: {', '.join(missing)}. "
                f"Use a file from the 'TrafficLabelling' folder. First columns found: {shown}"
            )
        width = len(header)
        for line in reader:
            if not line:
                continue
            read += 1
            if len(line) < width:
                skipped["short row"] += 1
                continue
            raw_label = norm_label(line[idx["label"]])
            label = mapping.get(raw_label)
            if label is None:
                skipped[f"unmapped label '{raw_label}'"] += 1
                continue
            try:
                ts, has_seconds = parse_timestamp(line[idx["timestamp"]], pm_before)
                duration_us = float(line[idx["flow duration"]])
                if not math.isfinite(duration_us) or duration_us < 0:
                    skipped["bad duration"] += 1
                    continue
                proto = PROTOCOLS.get(int(float(line[idx["protocol"]])), "OTHER")
                packets = int(float(line[idx["total fwd packets"]])) + int(float(line[idx["total backward packets"]]))
                size = int(float(line[idx["total length of fwd packets"]])) + int(
                    float(line[idx["total length of bwd packets"]])
                )
                sport = int(float(line[idx["source port"]]))
                dport = int(float(line[idx["destination port"]]))
            except (ValueError, OverflowError):
                skipped["unparsable row"] += 1
                continue
            if from_time or to_time:
                hhmm = datetime.fromtimestamp(ts, UTC).strftime("%H:%M")
                if (from_time and hhmm < from_time) or (to_time and hhmm > to_time):
                    skipped["outside time window"] += 1
                    continue
            src_ip = line[idx["source ip"]].strip()
            dst_ip = line[idx["destination ip"]].strip()
            if label != "normal" and src_ip.startswith(VICTIM_NET) and dst_ip == ATTACKER_NAT:
                src_ip, dst_ip, sport, dport = dst_ip, src_ip, dport, sport
                turned_around += 1
            rows.append(
                [
                    ts,
                    has_seconds,
                    round(duration_us / 1000.0, 3),
                    src_ip,
                    dst_ip,
                    sport,
                    dport,
                    proto,
                    packets,
                    size,
                    _flags(line, idx) if proto == "TCP" else "",
                    label,
                ]
            )

    rows.sort(key=lambda r: r[0])  # stable: file order is kept inside the same second
    minute_resolution = sum(1 for r in rows if not r[1])
    if spread_minutes:
        i = 0
        while i < len(rows):
            j = i
            while j < len(rows) and rows[j][0] == rows[i][0]:
                j += 1
            n = j - i
            if n > 1 and not rows[i][1]:
                base = rows[i][0]
                for k in range(i, j):
                    rows[k][0] = base + 60.0 * (k - i) / n
            i = j
    if limit:
        rows = rows[:limit]

    with open(dst, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(OUT_COLUMNS)
        for r in rows:
            writer.writerow([f"{r[0]:.3f}", *r[2:]])

    return {
        "read": read,
        "written": len(rows),
        "skipped": skipped,
        "labels": Counter(r[-1] for r in rows),
        "first_ts": rows[0][0] if rows else None,
        "last_ts": rows[-1][0] if rows else None,
        "minute_resolution": minute_resolution,
        "turned_around": turned_around,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Convert a CIC-IDS2017 TrafficLabelling CSV to a NetGuard flow CSV.")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--include-other", action="store_true", help="also keep web attacks, bot, infiltration, heartbleed")
    ap.add_argument("--from-time", metavar="HH:MM", help="keep flows from this time of day (24 h)")
    ap.add_argument("--to-time", metavar="HH:MM", help="keep flows until this time of day (24 h)")
    ap.add_argument("--pm-before", type=int, default=8, help="hours below this are afternoon (0 = file is 24 h)")
    ap.add_argument(
        "--spread-minutes", action="store_true", help="spread flows with minute-only timestamps over the minute"
    )
    ap.add_argument("--limit", type=int, help="keep only the first N flows (after sorting by time)")
    args = ap.parse_args(argv)
    try:
        s = convert(
            args.src,
            args.dst,
            include_other=args.include_other,
            from_time=args.from_time,
            to_time=args.to_time,
            pm_before=args.pm_before,
            spread_minutes=args.spread_minutes,
            limit=args.limit,
        )
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    def fmt(ts):
        return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%M:%S") if ts else "-"

    print(f"read={s['read']} written={s['written']} -> {args.dst}")
    print(f"labels: {dict(s['labels'])}")
    print(f"skipped: {dict(s['skipped'])}")
    print(f"time range: {fmt(s['first_ts'])} .. {fmt(s['last_ts'])}")
    if s["turned_around"]:
        print(f"note: {s['turned_around']} attack flows recorded server -> client were turned around.")
    if s["minute_resolution"] and args.spread_minutes:
        print(f"note: {s['minute_resolution']} flows have minute-only timestamps, spread over their minute.")
    elif s["minute_resolution"]:
        print(
            f"warning: {s['minute_resolution']} flows have minute-only timestamps; "
            "flows of one minute share one time. Use --spread-minutes to spread them."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
