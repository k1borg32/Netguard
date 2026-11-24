"""Small port-scan test files, written offline (owner: Member 1).

One scan and a little normal traffic, as a PCAP and as a labelled flow CSV with its ground-truth manifest. Nothing is
sent on a network: the packets go straight into a file. The files are the input of the end-to-end tests:

    ST-02  flow file with a known attack -> dashboard   data/flows/scan-small.csv (+ .manifest.json)
    ST-03  PCAP import -> dashboard                      data/pcap/portscan-small.pcap
    IT-09  the same through the running stack            tests/integration/test_e2e_import.py

The scan: 10.0.0.66 sends one SYN to 300 different ports of 10.0.0.5 in 8 s. The default port scan rule fires at 100
different ports in a 10 s window, so the scan is clearly above it. Time stands at 1,700,000,000 (a multiple of 10, so
the scan lies inside one 10 s window); use REPLAY_SPEED on the import to move it to the present for the dashboard.

Usage:
    python3 services/importer/make_scan_fixtures.py            # writes the three committed files
    python3 services/importer/make_scan_fixtures.py --attacker 10.99.1.2 --out-dir /tmp/x   # own attacker address

The output is the same on every run. Checksums in the PCAP are left at 0 (the importer does not check them).
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import socket
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START = 1_700_000_000.0
SCAN_PORTS = 300
SCAN_SECONDS = 8.0
TARGET = "10.0.0.5"
ATTACKER = "10.0.0.66"
CLIENTS = [f"10.0.0.{n}" for n in range(20, 25)]  # normal clients of the target
COLUMNS = ["ts_start", "duration_ms", "src_ip", "dst_ip", "src_port", "dst_port", "protocol", "packets", "bytes",
           "tcp_flags", "label"]  # fmt: skip


def flows(attacker: str = ATTACKER, target: str = TARGET) -> list[dict]:
    """The traffic as flows, sorted by time: 300 scan flows (1 SYN each) and 2 normal flows per second."""
    out = []
    step = SCAN_SECONDS / SCAN_PORTS
    for i in range(SCAN_PORTS):
        out.append(
            {"ts": START + i * step, "src": attacker, "dst": target, "sport": 40000 + i, "dport": 1000 + i,
             "packets": 1, "bytes": 54, "flags": "S", "duration_ms": 0.0, "label": "port_scan"}
        )  # fmt: skip
    for k in range(int(SCAN_SECONDS) * 2):
        out.append(
            {"ts": START + 0.25 + k * 0.5, "src": CLIENTS[k % len(CLIENTS)], "dst": target, "sport": 50000 + k,
             "dport": 443, "packets": 2, "bytes": 108, "flags": "SA", "duration_ms": 50.0, "label": "normal"}
        )  # fmt: skip
    return sorted(out, key=lambda f: (f["ts"], f["sport"]))


def _checksum(data: bytes) -> int:
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def _frame(src: str, dst: str, sport: int, dport: int, flags: int, ident: int) -> bytes:
    """Ethernet + IPv4 + TCP header, no payload: 54 bytes."""
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, ident & 0xFFFF, 0, 64, 6, 0,
                     socket.inet_aton(src), socket.inet_aton(dst))  # fmt: skip
    ip = ip[:10] + struct.pack("!H", _checksum(ip)) + ip[12:]
    tcp = struct.pack("!HHIIBBHHH", sport, dport, 1000, 0, 0x50, flags, 8192, 0, 0)
    return b"\x02\x00\x00\x00\x00\x02" + b"\x02\x00\x00\x00\x00\x01" + b"\x08\x00" + ip + tcp


def write_pcap(path: Path, attacker: str = ATTACKER, target: str = TARGET) -> int:
    """Classic Ethernet pcap. Returns the number of flows in it."""
    records = []
    for n, f in enumerate(flows(attacker, target)):
        records.append((f["ts"], _frame(f["src"], f["dst"], f["sport"], f["dport"], 0x02, n)))
        if f["packets"] == 2:  # normal flow: SYN, then ACK 50 ms later
            records.append((f["ts"] + 0.05, _frame(f["src"], f["dst"], f["sport"], f["dport"], 0x10, n)))
    records.sort(key=lambda r: r[0])
    data = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for ts, frame in records:
        sec = int(ts)
        data += struct.pack("<IIII", sec, round((ts - sec) * 1_000_000), len(frame), len(frame)) + frame
    path.write_bytes(data)
    return len(flows(attacker, target))


def write_csv(path: Path, attacker: str = ATTACKER, target: str = TARGET) -> int:
    """Labelled flow CSV (the format of data/flows/sample.csv). Returns the number of flows."""
    rows = flows(attacker, target)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(COLUMNS)
        for r in rows:
            writer.writerow([f"{r['ts']:.3f}", r["duration_ms"], r["src"], r["dst"], r["sport"], r["dport"], "TCP",
                             r["packets"], r["bytes"], r["flags"], r["label"]])  # fmt: skip
    return len(rows)


def write_manifest(csv_path: Path) -> dict:
    """The ground-truth manifest of the CSV, built the same way as for the dataset files."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from make_manifest import make_manifest

    notes = (
        "Synthetic, written by make_scan_fixtures.py: one port scan (300 SYN to 300 ports in 8 s) and normal "
        "traffic to the same target. Used by ST-02, ST-03 and IT-09."
    )
    manifest = make_manifest(str(csv_path), dataset=f"LABELLED/{csv_path.stem}", notes=notes)
    manifest["created_at"] = START  # fixed, so the file is the same on every run
    Path(f"{csv_path}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write the small port-scan test files (PCAP, CSV and manifest).")
    ap.add_argument("--attacker", default=ATTACKER, help="source address of the scan (default 10.0.0.66)")
    ap.add_argument("--out-dir", type=Path, help="default: data/pcap and data/flows of the repository")
    args = ap.parse_args(argv)
    try:
        ipaddress.ip_address(args.attacker)
    except ValueError:
        print(f"error: not an IP address: {args.attacker}", file=sys.stderr)
        return 1
    pcap_dir = args.out_dir or ROOT / "data" / "pcap"
    flow_dir = args.out_dir or ROOT / "data" / "flows"
    pcap_dir.mkdir(parents=True, exist_ok=True)
    flow_dir.mkdir(parents=True, exist_ok=True)
    n = write_pcap(pcap_dir / "portscan-small.pcap", args.attacker)
    write_csv(flow_dir / "scan-small.csv", args.attacker)
    manifest = write_manifest(flow_dir / "scan-small.csv")
    print(f"wrote {pcap_dir / 'portscan-small.pcap'}, {flow_dir / 'scan-small.csv'} (+ .manifest.json): {n} flows,")
    print(f"{len(manifest['episodes'])} episode(s), attacker {args.attacker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
