"""Ground-truth check: does a manifest match its flow CSV? (owner: Member 1, week 5)

Reads <file>.csv and <file>.csv.manifest.json and checks that
  * the manifest is valid against manifest.v1.json,
  * every attack-labelled flow lies inside exactly one episode of its class
    (time window, attacker address, target address),
  * the number of flows per episode equals params.flows of the manifest,
  * no episode is empty.
Normal flows from an attacker address inside an episode window are only counted
(background traffic of the attacker host), they are not an error.

Usage:
    python3 services/importer/check_manifest.py data/flows/<file>.csv
Exit code 0 = consistent, 1 = problems found.
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import sys
from collections import Counter
from pathlib import Path

from make_manifest import _validator  # the same schema check as the generator

REQUIRED = ("ts_start", "src_ip", "dst_ip", "label")
EPS = 1e-6


def ip_matches(ip: str, specs: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for spec in specs:
        if "/" in spec:
            try:
                if addr in ipaddress.ip_network(spec, strict=False):
                    return True
            except ValueError:
                continue
        elif spec == ip:
            return True
    return False


def _in_window(ep: dict, ts: float) -> bool:
    return ep["start"] - EPS <= ts <= ep["end"] + EPS


def check(csv_path: str, manifest_path: str | None = None) -> dict:
    manifest_path = manifest_path or f"{csv_path}.manifest.json"
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    result = {
        "problems": [],
        "attack_total": 0,
        "covered": 0,
        "uncovered": Counter(),
        "per_episode": {},
        "normal_in_episode": 0,
    }
    errors = sorted(_validator().iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        where = ".".join(str(p) for p in e.path) or "<root>"
        result["problems"].append(f"manifest does not match manifest.v1.json: {where}: {e.message}")
        return result

    episodes = manifest["episodes"]
    by_class: dict[str, list[dict]] = {}
    for ep in episodes:
        by_class.setdefault(ep["class"], []).append(ep)
    counted: Counter = Counter()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(missing)}")
        for r in reader:
            label = (r["label"] or "").strip()
            ts = float(r["ts_start"])
            src, dst = r["src_ip"].strip(), r["dst_ip"].strip()
            if label and label != "normal":
                result["attack_total"] += 1
                hit = next(
                    (
                        ep
                        for ep in by_class.get(label, ())
                        if _in_window(ep, ts) and ip_matches(src, ep["attackers"]) and ip_matches(dst, ep["targets"])
                    ),
                    None,
                )
                if hit is None:
                    result["uncovered"][label] += 1
                else:
                    counted[hit["episode_id"]] += 1
                    result["covered"] += 1
            elif any(_in_window(ep, ts) and ip_matches(src, ep["attackers"]) for ep in episodes):
                result["normal_in_episode"] += 1

    for ep in episodes:
        n = counted[ep["episode_id"]]
        declared = ep.get("params", {}).get("flows")
        result["per_episode"][ep["episode_id"]] = (n, declared)
        if n == 0:
            result["problems"].append(f"{ep['episode_id']}: no flow of the CSV lies inside this episode")
        elif declared is not None and n != declared:
            result["problems"].append(f"{ep['episode_id']}: {n} flows in the CSV, manifest says {declared}")
    if result["uncovered"]:
        result["problems"].append(f"attack flows outside every episode: {dict(result['uncovered'])}")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check a ground-truth manifest against its flow CSV.")
    ap.add_argument("src", help="flow CSV")
    ap.add_argument("--manifest", help="default: <src>.manifest.json")
    args = ap.parse_args(argv)
    try:
        r = check(args.src, args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"attack flows in the CSV: {r['attack_total']}, inside an episode: {r['covered']}")
    for ep_id, (n, declared) in r["per_episode"].items():
        print(f"  {ep_id:<18} csv={n:<8} manifest={declared}")
    print(f"normal flows from an attacker address inside episodes: {r['normal_in_episode']}")
    for p in r["problems"]:
        print(f"PROBLEM: {p}")
    print("OK" if not r["problems"] else "FAILED")
    return 0 if not r["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
