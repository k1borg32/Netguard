"""Cut a time slice out of a labelled flow CSV (owner: Member 1).

The dataset files are big (a whole attack day). The end-to-end checks (IT-04) and the demo need a small piece of
one attack with the normal traffic around it, and a manifest that belongs to exactly that piece. This tool cuts the
piece out and writes its manifest the same way make_manifest.py does.

Usage:
    # the first 120 s of an episode of the manifest next to the file, 30 s of normal traffic before and after
    python3 services/importer/slice_flows.py data/flows/cic-friday-portscan.csv data/flows/it04-portscan.csv \
        --episode port_scan-003 --pad 30 --max-seconds 120
    # or an explicit time range (epoch seconds of the CSV)
    python3 services/importer/slice_flows.py SRC DST --from 1499443000 --to 1499443300

Writes DST and DST.manifest.json. The slice keeps the flows of every class inside the range.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def slice_csv(src: str, dst: str, start: float, end: float) -> int:
    """Copy the rows with start <= ts_start <= end (header included). Returns the number of rows written."""
    written = 0
    with open(src, newline="", encoding="utf-8") as fin, open(dst, "w", newline="", encoding="utf-8") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        header = next(reader, None)
        if not header or "ts_start" not in header:
            raise ValueError("the CSV has no ts_start column")
        col = header.index("ts_start")
        writer.writerow(header)
        for row in reader:
            if not row:
                continue
            try:
                ts = float(row[col])
            except (ValueError, IndexError) as e:
                raise ValueError(f"unreadable ts_start in row {written + 2}: {row[col : col + 1]}") from e
            if start <= ts <= end:
                writer.writerow(row)
                written += 1
    return written


def episode_range(manifest_path: str, episode_id: str, pad: float, max_seconds: float | None) -> tuple[float, float]:
    """Time range of an episode: its start to its end (or start + max_seconds), plus pad on both sides."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for ep in manifest["episodes"]:
        if ep["episode_id"] == episode_id:
            end = ep["end"] if max_seconds is None else min(ep["end"], ep["start"] + max_seconds)
            return ep["start"] - pad, end + pad
    known = ", ".join(e["episode_id"] for e in manifest["episodes"])
    raise ValueError(f"no episode '{episode_id}' in {manifest_path} (episodes: {known})")


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%M:%S")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cut a time slice and its manifest out of a labelled flow CSV.")
    ap.add_argument("src", help="labelled flow CSV (output of convert_cic.py)")
    ap.add_argument("dst", help="the slice to write")
    ap.add_argument("--episode", help="episode ID in the manifest next to SRC")
    ap.add_argument("--manifest", help="default: <src>.manifest.json")
    ap.add_argument("--pad", type=float, default=30.0, help="seconds around the episode (default 30)")
    ap.add_argument("--max-seconds", type=float, help="use only the first N seconds of the episode")
    ap.add_argument("--from", dest="start", type=float, help="start of the range (epoch seconds)")
    ap.add_argument("--to", dest="end", type=float, help="end of the range (epoch seconds)")
    args = ap.parse_args(argv)

    try:
        if args.episode:
            start, end = episode_range(
                args.manifest or f"{args.src}.manifest.json", args.episode, args.pad, args.max_seconds
            )
        elif args.start is not None and args.end is not None:
            start, end = args.start, args.end
        else:
            print("error: give --episode, or --from and --to", file=sys.stderr)
            return 1
        n = slice_csv(args.src, args.dst, start, end)
        if n == 0:
            print(f"error: no flows between {_utc(start)} and {_utc(end)}", file=sys.stderr)
            return 1
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from make_manifest import make_manifest

        what = f"episode {args.episode}" if args.episode else "a time range"
        notes = (
            f"Slice of {Path(args.src).name} around {what}, {_utc(start)} to {_utc(end)} UTC. "
            "Labels as in the source file; episodes are rebuilt from the slice."
        )
        manifest = make_manifest(args.dst, dataset=f"LABELLED/{Path(args.dst).stem}", notes=notes)
        Path(f"{args.dst}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"wrote {args.dst}: {n} flows, {_utc(start)} .. {_utc(end)} UTC, {len(manifest['episodes'])} episode(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
