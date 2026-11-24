"""Detection quality (DQ-01 to DQ-03, NFR11): precision, recall and F1 per class against a ground-truth manifest.

Import one labelled flow file into a fresh stack without replay, so the detections carry the same flow time as the
manifest, and wait until the processor has caught up. Then:
    python tests/quality/evaluate.py data/flows/cic-friday-portscan.csv
The manifest is the file next to it (<file>.manifest.json). The detections are read from the stack database: every
detection whose window overlaps the time range of the file, so other data from the same time would be counted too.

Matching (test plan 3.6): a detection matches an episode when the class is the same, its source is one of the
episode's attackers (for a DDoS-like detection without a source: its destination is one of the targets) and its
window overlaps the episode, give or take one window. The results also go to results/quality/<file>.json.
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg

from netguard_common import validate_manifest

ROOT = Path(__file__).resolve().parents[2]
ATTACK_CLASSES = ("port_scan", "dos", "brute_force", "abnormal_traffic", "suspicious_pattern")


@dataclass(frozen=True)
class Detection:
    type: str
    src_ip: str | None
    dst_ip: str | None
    start: float  # window start and end, flow time
    end: float


def belongs(ip: str | None, entries: list[str]) -> bool:
    """entries are addresses or networks, as in the manifest."""
    if ip is None:
        return False
    address = ipaddress.ip_address(ip)
    return any(address in ipaddress.ip_network(entry, strict=False) for entry in entries)


def hits(d: Detection, episode: dict) -> bool:
    """Same attacker (or target, when the detection has no source) and overlapping time, whatever the class."""
    same_party = belongs(d.src_ip, episode["attackers"]) if d.src_ip else belongs(d.dst_ip, episode["targets"])
    tolerance = d.end - d.start
    return same_party and d.start <= episode["end"] + tolerance and d.end >= episode["start"] - tolerance


def f1(precision: float | None, recall: float | None) -> float:
    if not precision or not recall:
        return 0.0  # also when a class has episodes but no detections at all
    return 2 * precision * recall / (precision + recall)


def evaluate(detections: list[Detection], episodes: list[dict], hours: float, min_flows: int = 0) -> dict:
    """Episodes with fewer than min_flows labelled flows (params.flows, stray labels in the dataset) still make a
    detection that hits them correct, but they don't count for recall; they are listed separately."""
    # per episode: indexes of the detections that hit it, and of those that also have its class
    hit = [[i for i, d in enumerate(detections) if hits(d, e)] for e in episodes]
    right = [[i for i in hit[k] if detections[i].type == e["class"]] for k, e in enumerate(episodes)]
    correct = {i for found in right for i in found}
    hit_any = {i for found in hit for i in found}
    small = {k for k, e in enumerate(episodes) if e.get("params", {}).get("flows", min_flows) < min_flows}
    scored = [k for k in range(len(episodes)) if k not in small]

    per_class = {}
    for c in ATTACK_CLASSES:
        predicted = [i for i, d in enumerate(detections) if d.type == c]
        real = [k for k in scored if episodes[k]["class"] == c]
        if not predicted and not real:
            continue
        precision = sum(i in correct for i in predicted) / len(predicted) if predicted else None
        recall = sum(bool(right[k]) for k in real) / len(real) if real else None
        per_class[c] = {
            "detections": len(predicted),
            "episodes": len(real),
            "precision": precision,
            "recall": recall,
            "f1": f1(precision, recall) if real else None,
        }

    # rows: real class of every episode (counted once per predicted class), plus "normal" for detections that hit
    # no episode at all
    confusion: dict[str, Counter] = {}
    for k in scored:
        confusion.setdefault(episodes[k]["class"], Counter()).update({detections[i].type for i in hit[k]} or {"missed"})
    false_alarms = [d for i, d in enumerate(detections) if i not in hit_any]
    if false_alarms:
        confusion["normal"] = Counter(d.type for d in false_alarms)

    f1_scores = [m["f1"] for m in per_class.values() if m["f1"] is not None]
    matched = [len(right[k]) for k in scored if right[k]]
    return {
        "per_class": per_class,
        "macro_f1": statistics.fmean(f1_scores) if f1_scores else None,
        "confusion": confusion,
        "unclassified_episodes": sum(any(detections[i].type == "unknown" for i in hit[k]) for k in scored),
        "detections_per_matched_episode": {"avg": statistics.fmean(matched), "max": max(matched)} if matched else None,
        "false_alarms": len(false_alarms),
        "false_alarms_per_hour": len(false_alarms) / hours if hours > 0 else None,
        "small_episodes": [
            {"episode": episodes[k]["episode_id"], "flows": episodes[k]["params"]["flows"], "detected": bool(right[k])}
            for k in sorted(small)
        ],
    }


def time_range(flows: Path) -> tuple[float, float]:
    """First and last ts_start of the file, read the same way the importer reads it."""
    times = []
    with open(flows, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row["ts_start"].strip()
            try:
                times.append(float(raw))
            except ValueError:
                times.append(datetime.fromisoformat(raw.replace(" ", "T")).timestamp())
    if not times:
        raise ValueError(f"{flows} has no flows")
    return min(times), max(times)


def stack_conninfo() -> dict:
    """Credentials of the running stack from .env, the same file Compose uses."""
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            env[key.strip()] = value.strip()
    return {
        "host": "127.0.0.1",
        "port": 5432,
        "user": env["POSTGRES_USER"],
        "password": env["POSTGRES_PASSWORD"],
        "dbname": env["POSTGRES_DB"],
    }


def stored_detections(first: float, last: float) -> list[Detection]:
    with psycopg.connect(**stack_conninfo()) as db:
        rows = db.execute(
            "SELECT type, host(src_ip), host(dst_ip), extract(epoch FROM window_start), extract(epoch FROM window_end) "
            "FROM detections WHERE window_end >= to_timestamp(%s) AND window_start <= to_timestamp(%s)",
            (first, last),
        ).fetchall()
    return [Detection(t, src, dst, float(start), float(end)) for t, src, dst, start, end in rows]


def ratio(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def print_report(name: str, result: dict) -> None:
    print(f"\n{name}\n\n| Class | Episodes | Detections | Precision | Recall | F1 |")
    print("|---|---|---|---|---|---|")
    for c, m in result["per_class"].items():
        print(
            f"| {c} | {m['episodes']} | {m['detections']} | {ratio(m['precision'])} | {ratio(m['recall'])} "
            f"| {ratio(m['f1'])} |"
        )
    print(f"\nMacro F1 over the classes in the manifest: {ratio(result['macro_f1'])}")
    print(f"False alarms (detections outside every episode): {result['false_alarms']}", end="")
    print(f", {ratio(result['false_alarms_per_hour'])} per hour of data")
    print(f"Episodes hit by an unknown detection (detected but not classified): {result['unclassified_episodes']}")
    print(f"Detections per matched episode: {result['detections_per_matched_episode']}")
    if result["small_episodes"]:
        small = ", ".join(
            f"{s['episode']} ({s['flows']} flows, {'detected' if s['detected'] else 'missed'})"
            for s in result["small_episodes"]
        )
        print(f"Left out of recall, too few flows: {small}")
    columns = sorted({c for row in result["confusion"].values() for c in row} - {"missed"}) + ["missed"]
    print(f"\n| Real \\ predicted | {' | '.join(columns)} |\n|---|{'---|' * len(columns)}")
    for real, row in result["confusion"].items():
        print(f"| {real} | {' | '.join(str(row.get(c, 0)) for c in columns)} |")


def main() -> None:
    parser = argparse.ArgumentParser(description="Precision, recall and F1 per class against a ground-truth manifest.")
    parser.add_argument("flows", type=Path, help="the labelled flow CSV that was imported")
    parser.add_argument("--min-flows", type=int, default=0, help="leave episodes with fewer flows out of recall")
    args = parser.parse_args()

    manifest = validate_manifest(json.loads(Path(f"{args.flows}.manifest.json").read_text(encoding="utf-8")))
    first, last = time_range(args.flows)
    detections = stored_detections(first, last)
    result = evaluate(detections, manifest["episodes"], (last - first) / 3600, args.min_flows)
    print_report(args.flows.name, result)

    out = ROOT / "results" / "quality"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.flows.stem}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
