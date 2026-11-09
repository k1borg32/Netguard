"""DQ-08: every detection explains itself (F09).

Runs the detection engine on flow files at the default config, the same way sweep.py does, and checks every
detection: a valid detection.v1 message, the observed values with the threshold and the ratio to it (and the z-score
for the statistical method), the window, a source or a destination, severity, confidence and the explanation.

    python tests/quality/check_content.py data/flows/cic-friday-portscan.csv data/flows/cic-monday-normal.csv
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import yaml
from sweep import ROOT, detect, read_flows

from netguard_common import SchemaError, validate_detection


def problems(d: dict) -> list[str]:
    out = []
    try:
        validate_detection(d)
    except SchemaError as e:
        out.append(str(e))
    features = d["features"]
    if "threshold" not in features or "ratio" not in features:
        out.append("no threshold or ratio in the features")
    if len(features) < 3:
        out.append("no observed values next to the threshold")
    if d["method"] == "statistical" and "zscore" not in features:
        out.append("statistical detection without its z-score")
    if d["src_ip"] is None and d["dst_ip"] is None:
        out.append("neither source nor destination")
    if d["window"]["end"] <= d["window"]["start"]:
        out.append("empty window")
    if not d["explanation"].strip():
        out.append("empty explanation")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="DQ-08: check the content of every detection.")
    parser.add_argument("flows", type=Path, nargs="+", help="flow CSV files")
    args = parser.parse_args()

    raw = yaml.safe_load((ROOT / "config/detection.yaml").read_text(encoding="utf-8"))
    failed = 0
    for path in args.flows:
        found = detect(read_flows(path), raw)
        bad = [(d["detection_id"], p) for d in found if (p := problems(d))]
        by_type = dict(Counter(d["type"] for d in found))
        print(f"{path.name}: {len(found)} detections {by_type}, {len(bad)} with problems")
        for detection_id, p in bad[:10]:
            print(f"  {detection_id}: {'; '.join(p)}")
        failed += len(bad)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
