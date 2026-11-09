"""Threshold sweep (DQ-04): precision and recall of one rule over a range of thresholds, on a labelled flow file.

Runs the detection engine of the processor directly on the file, without the stack, so one value takes seconds
instead of a full import. The engine gets the flows like the processor does: in batches of 500 with a clock that
moves at the import speed (about 11,400 flows/s, measured in week 4), and keeps one row per detection with its
highest severity, like the persister. The scoring is the one from evaluate.py (test plan 3.6). At the default
config this gives the same numbers as the full stack (week 5, Docs/TestReport section 3).

With --normal it also runs a normal-only file, where every detection is a false alarm, and counts what the
operator would get there (DQ-02): detections of the swept type per hour, alerts per 10 min and HIGH/CRITICAL alerts.

    python tests/quality/sweep.py data/flows/cic-friday-portscan.csv rules.port_scan.unique_dst_ports_threshold \
        20 50 100 200 400 --normal data/flows/cic-monday-normal.csv --min-flows 10
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
for folder in ("tests/quality", "services/processor", "services/importer"):
    sys.path.insert(0, str(ROOT / folder))

from detection_engine import DetectionEngine, parse_config  # noqa: E402
from evaluate import Detection, evaluate, ratio, time_range  # noqa: E402
from importer import normalise_row  # noqa: E402

BATCH = 500
IMPORT_RATE = 11_400  # flows per second, the speed of the importer on the Friday file
SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def read_flows(path: Path) -> list[dict]:
    """The fields the engine reads, normalised like the importer does it."""
    flows = []
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            flow = normalise_row(row)
            flows.append({**flow, "trace_id": f"t{i:08d}", "ingested_at": 0.0})
    return flows


def minutes_of(path: Path) -> float:
    first, last = time_range(path)
    return (last - first) / 60


def types_of(key: str) -> list[str]:
    """Detection types a parameter belongs to: rules.<type>.<name>, or the statistical method."""
    parts = key.split(".")
    if parts[0] == "rules" and len(parts) == 3:
        return [parts[1]]
    if parts[0] == "statistical":
        return ["abnormal_traffic", "unknown"]
    raise SystemExit(f"{key}: only rules.<type>.<name> and statistical.<name> can be swept")


def detect(flows: list[dict], raw_config: dict) -> list[dict]:
    """All detections, one per detection_id with its highest severity, with "alert" true when any version of it
    raised one (the persister keeps at most one alert per detection)."""
    engine = DetectionEngine(parse_config(raw_config))
    found: dict[str, dict] = {}

    def keep(detections: list[dict]) -> None:
        for d in detections:
            old = found.get(d["detection_id"])
            if old is None or SEVERITY_RANK[d["severity"]] > SEVERITY_RANK[old["severity"]]:
                found[d["detection_id"]] = {**d, "alert": d["alert"] or (old is not None and old["alert"])}
            elif d["alert"]:
                old["alert"] = True

    clock = 1_000_000.0  # any start works, only the differences matter
    for start in range(0, len(flows), BATCH):
        for flow in flows[start : start + BATCH]:
            flow["ingested_at"] = clock
            engine.add(flow, clock)
            clock += 1 / IMPORT_RATE
        keep(engine.evaluate(clock))
    keep(engine.evaluate(clock + 3600))  # an hour later every window is closed
    return list(found.values())


def as_detection(d: dict) -> Detection:
    return Detection(d["type"], d["src_ip"], d["dst_ip"], d["window"]["start"], d["window"]["end"])


def on_normal(found: list[dict], minutes: float) -> dict:
    """Detections per hour by type, alerts per 10 min and HIGH/CRITICAL alerts on a normal-only file."""
    alerts = [d for d in found if d["alert"]]
    return {
        "per_hour": {t: n * 60 / minutes for t, n in Counter(d["type"] for d in found).items()},
        "alerts": len(alerts),
        "alerts_per_10_min": len(alerts) * 10 / minutes,
        "high_alerts": sum(d["severity"] in ("HIGH", "CRITICAL") for d in alerts),
    }


def with_value(raw: dict, key: str, value: float) -> dict:
    changed = copy.deepcopy(raw)
    *path, last = key.split(".")
    section = changed
    for part in path:
        section = section[part]
    section[last] = type(section[last])(value)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Precision and recall of one rule over a range of thresholds.")
    parser.add_argument("flows", type=Path, help="labelled flow CSV with its .manifest.json next to it")
    parser.add_argument("key", help="parameter in detection.yaml, e.g. rules.port_scan.unique_dst_ports_threshold")
    parser.add_argument("values", type=float, nargs="+")
    parser.add_argument("--normal", type=Path, help="normal-only flow CSV for the false alarms and alerts")
    parser.add_argument("--min-flows", type=int, default=0, help="leave episodes with fewer flows out of recall")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="another change to the config, kept for every value, e.g. rules.dos.window_s=10",
    )
    args = parser.parse_args()

    raw = yaml.safe_load((ROOT / "config/detection.yaml").read_text(encoding="utf-8"))
    for change in args.set:
        key, _, value = change.partition("=")
        raw = with_value(raw, key, float(value))
    manifest = json.loads(Path(f"{args.flows}.manifest.json").read_text(encoding="utf-8"))
    types = types_of(args.key)
    flows = read_flows(args.flows)
    hours = minutes_of(args.flows) / 60
    normal = read_flows(args.normal) if args.normal else None

    print(f"\n{args.flows.name}: {args.key}, normal file: {args.normal.name if args.normal else '-'}")
    print(f"other changes: {', '.join(args.set) or 'none'}\n")
    # the last three columns are from the normal file
    print("| Value | Type | Detections | Precision | Recall | F1 | Same type / h | Alerts / 10 min | HIGH+ alerts |")
    print("|---|---|---|---|---|---|---|---|---|")
    results = []
    for value in args.values:
        config = with_value(raw, args.key, value)
        found = detect([dict(f) for f in flows], config)
        result = evaluate([as_detection(d) for d in found], manifest["episodes"], hours, args.min_flows)
        quiet = on_normal(detect([dict(f) for f in normal], config), minutes_of(args.normal)) if normal else None
        for t in types:
            m = result["per_class"].get(t, {"precision": None, "recall": None, "f1": None})
            n = sum(d["type"] == t for d in found)
            alarms = "-" if quiet is None else f"{quiet['per_hour'].get(t, 0.0):.1f}"
            alerts = "-" if quiet is None else f"{quiet['alerts_per_10_min']:.1f}"
            high = "-" if quiet is None else quiet["high_alerts"]
            print(
                f"| {value:g} | {t} | {n} | {ratio(m['precision'])} | {ratio(m['recall'])} | {ratio(m['f1'])} "
                f"| {alarms} | {alerts} | {high} |"
            )
        results.append({"value": value, "result": result, "normal": quiet})

    out = ROOT / "results" / "quality"
    out.mkdir(parents=True, exist_ok=True)
    name = f"sweep-{args.flows.stem}-{args.key.split('.')[-1]}.json"
    (out / name).write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
