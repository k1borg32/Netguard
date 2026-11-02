"""Ground-truth manifest from a labelled flow CSV (owner: Member 1).

Reads a flow CSV that the importer accepts (columns ts_start, src_ip, dst_ip, dst_port,
label) and writes <file>.manifest.json, validated against manifest.v1.json (test plan 3.6).

One episode = one continuous attack of one class from one attacker. Flows of the same
(class, attacker) belong to one episode until a gap longer than --gap seconds starts a
new one. start/end are the ts_start (flow time) of the first and last attack flow, in
the time of the CSV. Everything that is not inside an episode counts as normal traffic.

Usage:
    python3 services/importer/make_manifest.py data/flows/<file>.csv

The manifest belongs to exactly that CSV: convert the dataset with fixed options first
(for example --spread-minutes), because the options change the timestamps.
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from jsonschema import Draft202012Validator

CLASSES = ("port_scan", "dos", "brute_force", "abnormal_traffic", "suspicious_pattern")
REQUIRED = ("ts_start", "src_ip", "dst_ip", "dst_port", "label")


def _validator() -> Draft202012Validator:
    raw = resources.files("netguard_common").joinpath("schemas/manifest.v1.json").read_text()
    schema = json.loads(raw)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def collapse_hosts(ips: set[str], max_hosts: int) -> list[str]:
    """Few hosts: list them. Many hosts: the /24 (IPv4) or /64 (IPv6) networks they are in."""
    if len(ips) <= max_hosts:
        return sorted(ips)
    nets = set()
    for ip in ips:
        try:
            addr = ipaddress.ip_address(ip)
            prefix = 24 if addr.version == 4 else 64
            nets.add(str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False)))
        except ValueError:
            nets.add(ip)
    return sorted(nets)


def build_episodes(rows, gap_s: float = 120.0, max_hosts: int = 50) -> list[dict]:
    open_eps: dict[tuple[str, str], dict] = {}
    done: list[dict] = []
    for r in rows:
        label = (r.get("label") or "").strip()
        if not label or label == "normal":
            continue
        if label not in CLASSES:
            raise ValueError(f"unknown attack label '{label}'")
        ts = float(r["ts_start"])
        key = (label, r["src_ip"].strip())
        ep = open_eps.get(key)
        if ep is not None and ts - ep["end"] > gap_s:
            done.append(open_eps.pop(key))
            ep = None
        if ep is None:
            ep = {
                "class": label,
                "attacker": key[1],
                "start": ts,
                "end": ts,
                "targets": set(),
                "ports": set(),
                "flows": 0,
            }
            open_eps[key] = ep
        ep["start"] = min(ep["start"], ts)
        ep["end"] = max(ep["end"], ts)
        ep["targets"].add(r["dst_ip"].strip())
        ep["ports"].add(r["dst_port"].strip())
        ep["flows"] += 1
    done.extend(open_eps.values())
    done.sort(key=lambda e: (e["start"], e["class"]))

    counters: Counter = Counter()
    episodes = []
    for e in done:
        counters[e["class"]] += 1
        episodes.append(
            {
                "episode_id": f"{e['class']}-{counters[e['class']]:03d}",
                "class": e["class"],
                "attackers": [e["attacker"]],
                "targets": collapse_hosts(e["targets"], max_hosts),
                "start": e["start"],
                "end": e["end"],
                "params": {
                    "flows": e["flows"],
                    "distinct_dst_ports": len(e["ports"]),
                    "distinct_targets": len(e["targets"]),
                    "gap_s": gap_s,
                },
            }
        )
    return episodes


def make_manifest(
    src: str, *, dataset: str | None = None, gap_s: float = 120.0, max_hosts: int = 50, notes: str = ""
) -> dict:
    """Build and validate the manifest of one flow CSV. Raises ValueError for a wrong file."""
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(missing)}")
        episodes = build_episodes(reader, gap_s, max_hosts)
    manifest: dict = {
        "schema_version": 1,
        "dataset": dataset or f"LABELLED/{Path(src).stem}",
        "source": "flowfile",
        "seed": None,
        "created_at": round(time.time(), 3),
        "episodes": episodes,
    }
    if notes:
        manifest["notes"] = notes
    errors = sorted(_validator().iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        where = ".".join(str(p) for p in e.path) or "<root>"
        raise ValueError(f"manifest does not match manifest.v1.json: {where}: {e.message}")
    return manifest


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%M:%S")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write the ground-truth manifest of a labelled flow CSV.")
    ap.add_argument("src", help="flow CSV (output of convert_cic.py)")
    ap.add_argument("--out", help="default: <src>.manifest.json")
    ap.add_argument("--dataset", help="dataset ID (default: LABELLED/<file name>)")
    ap.add_argument("--gap", type=float, default=120.0, help="seconds without attack flows that end an episode")
    ap.add_argument("--max-hosts", type=int, default=50, help="more hosts than this are written as /24 networks")
    ap.add_argument("--notes", default="", help="free text: where the labels come from, how it was checked")
    args = ap.parse_args(argv)
    try:
        manifest = make_manifest(
            args.src, dataset=args.dataset, gap_s=args.gap, max_hosts=args.max_hosts, notes=args.notes
        )
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    out = args.out or f"{args.src}.manifest.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"wrote {out}: {len(manifest['episodes'])} episodes (UTC flow time)")
    for e in manifest["episodes"]:
        p = e["params"]
        print(
            f"  {e['episode_id']:<16} {_utc(e['start'])} .. {_utc(e['end'])}  "
            f"{e['end'] - e['start']:>7.0f}s  attacker={','.join(e['attackers'])}  "
            f"targets={p['distinct_targets']}  ports={p['distinct_dst_ports']}  flows={p['flows']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
