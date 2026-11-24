"""Import speed on large files (PT-07, owner: Member 1).

How fast does the importer read, check and encode a big file, and how much memory does it need? Three commands:

    # 1. make big test files (into data/tmp/, which git ignores and the importer container can read)
    python tests/performance/import_speed.py make-csv data/tmp/big.csv --flows 1000000
    python tests/performance/import_speed.py make-pcap data/tmp/big.pcap --mb 150 --pkts-per-flow 10

    # 2. importer only, without a broker: parse + check + encode. Own process, so the peak memory is clean
    python tests/performance/import_speed.py measure data/tmp/big.csv data/tmp/big.pcap
    python tests/performance/import_speed.py measure data/tmp/big.csv --schema-only   # the old way, for comparison

    # 3. the whole way into the broker (stack running with `make up`): `make import` timed from the importer's own log
    python tests/performance/import_speed.py stack data/tmp/big.csv

The tables go to stdout (copy them into the test report). Numbers depend on the machine: the machine is part of the
result (printed), and we never compare numbers from different machines (test plan 3.7).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import resource
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "importer"))
START = 1_700_000_000.0
COLUMNS = ["ts_start", "duration_ms", "src_ip", "dst_ip", "src_port", "dst_port", "protocol", "packets", "bytes",
           "tcp_flags", "label"]  # fmt: skip


def _ip(n: int) -> str:
    return f"10.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"


def make_csv(path: Path, flows: int, seed: int = 1) -> None:
    """Flow CSV with `flows` rows: about 100 flows/s from many sources, no attack (nothing to detect, only to read)."""
    rng = random.Random(seed)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for i in range(flows):
            w.writerow([f"{START + i / 100:.3f}", round(rng.random() * 500, 1), _ip(rng.randrange(1, 5000)),
                        _ip(rng.randrange(1, 200) + 0x10000), rng.randrange(1024, 65535),
                        rng.choice((80, 443, 53, 22, 8080)), "TCP", rng.randrange(1, 50),
                        rng.randrange(60, 60000), "SA", "normal"])  # fmt: skip


def _checksum(data: bytes) -> int:
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def _frame(src: str, dst: str, sport: int, dport: int, flags: int) -> bytes:
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 64, 6, 0, socket.inet_aton(src), socket.inet_aton(dst))
    ip = ip[:10] + struct.pack("!H", _checksum(ip)) + ip[12:]
    tcp = struct.pack("!HHIIBBHHH", sport, dport, 1000, 0, 0x50, flags, 8192, 0, 0)
    return b"\x02\x00\x00\x00\x00\x02\x02\x00\x00\x00\x00\x01\x08\x00" + ip + tcp


def make_pcap(path: Path, megabytes: float, pkts_per_flow: int, seed: int = 1) -> tuple[int, int]:
    """Classic pcap of about `megabytes` MB: 70-byte records, `pkts_per_flow` packets in every flow.

    1 packet per flow is the worst case for memory (every packet is a new flow). Returns (packets, flows).
    """
    rng = random.Random(seed)
    packets = int(megabytes * 1_000_000 // 70)
    flows = max(1, packets // pkts_per_flow)
    frames = []
    for _ in range(min(flows, 50_000)):  # a pool of different flows, reused with other ports for the rest
        frames.append((_ip(rng.randrange(1, 5000)), _ip(rng.randrange(1, 200) + 0x10000)))
    with open(path, "wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        buf = bytearray()
        for n in range(packets):
            flow = n % flows
            src, dst = frames[flow % len(frames)]
            sport = 1024 + (flow // len(frames)) % 60000 + (flow // (len(frames) * 60000)) * 7
            frame = _frame(src, dst, sport & 0xFFFF, 443, 0x10)
            ts = START + n / 20000
            sec = int(ts)
            buf += struct.pack("<IIII", sec, round((ts - sec) * 1_000_000), len(frame), len(frame)) + frame
            if len(buf) > 8_000_000:
                f.write(buf)
                buf.clear()
        f.write(buf)
    return packets, flows


def _peak_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1_000_000 if platform.system() == "Darwin" else peak / 1000  # bytes on macOS, KB on Linux


def _run_child(path: str, schema_only: bool = False) -> None:
    """Importer work without the broker: read, normalise, validate, encode. Prints one JSON line.

    schema_only=True checks every flow with the JSON schema only (how the importer worked before the fast check).
    """
    import importer

    from netguard_common.broker import encode
    from netguard_common.messages import SchemaError, validate_flow

    check = validate_flow if schema_only else importer.check_flow

    warnings: list[str] = []
    accepted = rejected = 0
    t0 = time.perf_counter()
    first = None
    error = None
    try:
        for index, (kind, rec, source) in enumerate(importer._raw_records(path, warnings)):
            if first is None:
                first = time.perf_counter() - t0  # PCAP: the time to read and group the whole capture
            try:
                fields = importer.normalise_row(rec) if kind == "row" else rec
                flow = importer.finalise_flow(fields, os.path.basename(path), index, time.time(), "0" * 32, source)
                check(flow)
                encode(flow)
            except (ValueError, SchemaError):
                rejected += 1
                continue
            accepted += 1
    except importer.InputError as e:
        error = str(e)
    total = time.perf_counter() - t0
    print(json.dumps({"accepted": accepted, "rejected": rejected, "seconds": total, "first_s": first,
                      "peak_mb": _peak_mb(), "error": error, "warnings": warnings}))  # fmt: skip


def _machine() -> str:
    try:
        cpus = os.cpu_count()
        return f"{platform.system()} {platform.machine()}, {cpus} CPUs, Python {platform.python_version()}"
    except Exception:
        return platform.platform()


def measure(paths: list[str], schema_only: bool = False) -> None:
    print(f"Machine: {_machine()}" + (" (JSON schema check only)" if schema_only else "") + "\n")
    print("| File | Size (MB) | Flows accepted | Rejected | Seconds | Flows/s | Peak memory (MB) | Note |")
    print("|---|---|---|---|---|---|---|---|")
    for p in paths:
        size = os.path.getsize(p) / 1_000_000
        child = [sys.executable, __file__, "_child", p] + (["--schema-only"] if schema_only else [])
        out = subprocess.run(child, capture_output=True, text=True, check=False)
        if out.returncode != 0 or not out.stdout.strip():
            print(f"| {p} | {size:.0f} | failed | | | | | {out.stderr.strip()[-120:]} |")
            continue
        r = json.loads(out.stdout.strip().splitlines()[-1])
        if r["error"]:
            print(f"| {p} | {size:.0f} | 0 | 0 | {r['seconds']:.1f} | - | {r['peak_mb']:.0f} | {r['error'][:90]} |")
            continue
        rate = r["accepted"] / r["seconds"] if r["seconds"] else 0
        note = f"reading the capture took {r['first_s']:.1f} s" if p.lower().endswith((".pcap", ".cap")) else ""
        print(f"| {p} | {size:.0f} | {r['accepted']:,} | {r['rejected']:,} | {r['seconds']:.1f} | {rate:,.0f} | "
              f"{r['peak_mb']:.0f} | {note} |")  # fmt: skip


def stack(paths: list[str]) -> None:
    """Whole import into the running stack, timed from the importer's own log lines (container start left out)."""
    print(f"Machine: {_machine()}\n")
    print("| File | Flows accepted | Seconds (started -> finished) | Flows/s |")
    print("|---|---|---|---|")
    for p in paths:
        rel = os.path.relpath(p, ROOT)
        cmd = ["docker", "compose", "--profile", "import", "run", "--rm", "-e", f"FLOW_FILE=/app/{rel}", "importer"]
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
        started = finished = None
        accepted = 0
        for line in out.stdout.splitlines():
            if not line.startswith("{"):
                continue
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if j.get("msg") == "importer started":
                started = j["ts"]
            elif j.get("msg") == "importer finished":
                finished, accepted = j["ts"], j.get("accepted", 0)
        if started is None or finished is None:
            print(f"| {rel} | failed: {(out.stdout + out.stderr).strip()[-150:]} | | |")
            continue
        secs = finished - started
        print(f"| {rel} | {accepted:,} | {secs:.1f} | {accepted / secs:,.0f} |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("make-csv", help="write a big flow CSV")
    c.add_argument("out", type=Path)
    c.add_argument("--flows", type=int, default=1_000_000)
    p = sub.add_parser("make-pcap", help="write a big pcap")
    p.add_argument("out", type=Path)
    p.add_argument("--mb", type=float, default=150)
    p.add_argument("--pkts-per-flow", type=int, default=10)
    m = sub.add_parser("measure", help="importer only (no broker): speed and peak memory per file")
    m.add_argument("files", nargs="+")
    m.add_argument(
        "--schema-only", action="store_true", help="check every flow with the JSON schema only (the old way)"
    )
    s = sub.add_parser("stack", help="whole import into the running stack (make up first)")
    s.add_argument("files", nargs="+")
    ch = sub.add_parser("_child")
    ch.add_argument("file")
    ch.add_argument("--schema-only", action="store_true")
    args = ap.parse_args()

    if args.cmd == "make-csv":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        make_csv(args.out, args.flows)
        print(f"wrote {args.out}: {args.flows:,} flows, {args.out.stat().st_size / 1_000_000:.0f} MB")
    elif args.cmd == "make-pcap":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        packets, flows = make_pcap(args.out, args.mb, args.pkts_per_flow)
        print(f"wrote {args.out}: {packets:,} packets, {flows:,} flows, {args.out.stat().st_size / 1_000_000:.0f} MB")
    elif args.cmd == "measure":
        measure(args.files, args.schema_only)
    elif args.cmd == "stack":
        stack(args.files)
    else:
        _run_child(args.file, args.schema_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
