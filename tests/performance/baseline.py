"""Performance baseline (PT-01, PT-02): steady load from the load generator, measured from outside the services.

For every rate the load generator runs for warm-up + measurement time. Every 5 s the script samples the
consumer lag of the processor and persister groups and `docker stats`. After the run it waits until both
groups have caught up, then collects for the measurement window:
  - flows sent (load generator summary) and stored (network_flows), so lost = sent - stored
  - flows the processor dropped as late (its window had already closed), from its own counters
  - detection latency (NFR02), all detections and per type, from the processor's "detection" log lines.
    latency_s there is creation time - last_ingested_at, taken when the detection is made (spec 15)
  - CPU and memory per container

The detection_latency view is read for the same window too, only to compare: until #65 the persister moved
last_ingested_at when a detection escalated, so escalated detections got a negative latency there.

Usage (stack running with `make up`, venv active):
    python tests/performance/baseline.py --rates 100 1000 5000
Raw samples and summary.json go to results/perf/<date-time>/, the tables for the test report to stdout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import statistics
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from confluent_kafka import Consumer, ConsumerGroupTopicPartitions, KafkaException, TopicPartition
from confluent_kafka.admin import AdminClient

from netguard_common import topics

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "--profile", "perf"]
BOOTSTRAP = os.getenv("BROKER_BOOTSTRAP", "127.0.0.1:19092")
# The broker advertises localhost:19092 but the port is published on 127.0.0.1 only. Without v4 librdkafka tries
# ::1 first and every new connection waits about 2 s for that to fail.
KAFKA = {"bootstrap.servers": BOOTSTRAP, "broker.address.family": "v4"}
SAMPLE_EVERY_S = 5.0
GROUPS = {"processor": [topics.FLOWS_RAW], "persister": [topics.FLOWS_RAW, topics.DETECTIONS]}
MEMORY_UNITS = {"GiB": 2**10, "MiB": 1.0, "KiB": 2**-10, "GB": 1e9 / 2**20, "MB": 1e6 / 2**20, "kB": 1e3 / 2**20}
MEMORY_UNITS["B"] = 2**-20  # last: every other unit ends with "B" too


class LagReader:
    """Consumer lag of a group: newest offset minus committed offset, summed over the group's partitions."""

    def __init__(self) -> None:
        self.admin = AdminClient(KAFKA)
        self.offsets = Consumer({**KAFKA, "group.id": "perf-baseline"})

    def lag(self, group: str, topic_names: list[str]) -> int:
        wanted = [TopicPartition(t, p) for t in topic_names for p in range(topics.PARTITIONS[t])]
        request = ConsumerGroupTopicPartitions(group, wanted)
        committed = self.admin.list_consumer_group_offsets([request])[group].result(timeout=10).topic_partitions
        total = 0
        for tp in committed:
            low, high = self.offsets.get_watermark_offsets(TopicPartition(tp.topic, tp.partition), timeout=10)
            done = tp.offset if tp.offset >= 0 else low  # nothing committed yet: all of it is still to do
            total += max(0, high - done)
        return total


def json_lines(text: str) -> list[dict]:
    entries = []
    for line in text.splitlines():
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue  # compose progress lines, tracebacks
    return entries


def memory_mib(text: str) -> float:
    text = text.strip()
    for unit, mib in MEMORY_UNITS.items():
        if text.endswith(unit):
            return float(text[: -len(unit)]) * mib
    return 0.0


def docker_stats() -> list[dict]:
    command = ["docker", "stats", "--no-stream", "--format", "{{json .}}"]
    rows = []
    for stat in json_lines(subprocess.run(command, capture_output=True, text=True, timeout=60).stdout):
        if not stat["Name"].startswith("netguard-"):
            continue
        try:
            cpu = float(stat["CPUPerc"].rstrip("%"))
        except ValueError:
            continue  # "--" while a container is starting or stopping
        rows.append({"container": stat["Name"], "cpu_pct": cpu, "mem_mib": memory_mib(stat["MemUsage"].split("/")[0])})
    return rows


class Sampler(threading.Thread):
    """Lag of both groups and docker stats every SAMPLE_EVERY_S seconds, until stop is set."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.lag_reader = LagReader()
        self.lag_rows: list[dict] = []
        self.stats_rows: list[dict] = []
        self.missed_samples = 0
        self.stop = threading.Event()

    def run(self) -> None:
        while not self.stop.is_set():
            t = time.time()
            try:
                lags = {group: self.lag_reader.lag(group, topic_names) for group, topic_names in GROUPS.items()}
                stats = docker_stats()
            except (KafkaException, TimeoutError, subprocess.SubprocessError):
                self.missed_samples += 1  # one slow answer shouldn't end the sampling
            else:
                self.lag_rows += [{"t": t, "group": group, "lag": lag} for group, lag in lags.items()]
                self.stats_rows += [{"t": t, **row} for row in stats]
            self.stop.wait(max(0.0, SAMPLE_EVERY_S - (time.time() - t)))

    def last_lag(self) -> dict[str, int]:
        return {row["group"]: row["lag"] for row in self.lag_rows[-len(GROUPS) :]}


def run_generators(rate: int, duration: int, generators: int) -> list[list[dict]]:
    """Starts the load generator containers (the rate is split between them) and returns their log lines."""
    env = ["-e", f"LOAD_RATE={rate // generators}", "-e", f"LOAD_DURATION_S={duration}"]
    command = [*COMPOSE, "run", "--rm", "-T", *env, "loadgen"]
    output = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True, "errors": "replace"}
    runs = [subprocess.Popen(command, cwd=ROOT, **output) for _ in range(generators)]
    return [json_lines(run.communicate(timeout=duration + 300)[0]) for run in runs]


def wait_until_caught_up(sampler: Sampler, timeout_s: float) -> float | None:
    """Seconds until both groups have read and committed everything, None if they don't catch up in time."""
    started = time.time()
    while time.time() - started < timeout_s:
        lag = sampler.last_lag()
        if len(lag) == len(GROUPS) and max(lag.values()) == 0:
            return round(time.time() - started, 1)
        time.sleep(1)
    return None


def processor_log(since: float) -> list[dict]:
    """JSON log lines of every processor instance: "detection" for every detection it sends (with latency_s
    measured at that moment) and "engine stats" with its counters every 30 s."""
    started = datetime.fromtimestamp(since, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    command = [*COMPOSE, "logs", "--no-color", "--since", started, "processor"]
    out = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=120).stdout
    entries = []
    for line in out.splitlines():
        instance, _, text = line.partition("|")  # "processor-1  | {...}"
        entries += [{**entry, "instance": instance.strip()} for entry in json_lines(text)]
    return entries


def late_flows(log: list[dict], run_start: float, run_end: float) -> int | None:
    """Flows the processor dropped during the run because their window had already closed (its counters are
    cumulative per instance)."""
    total = 0
    for instance in {e["instance"] for e in log}:
        stats = [e for e in log if e["instance"] == instance and e.get("msg") == "engine stats"]
        before = [e["late_flows"] for e in stats if e["ts"] <= run_start]
        after = [e["late_flows"] for e in stats if e["ts"] >= run_end]
        if not before or not after:
            return None
        total += after[0] - before[-1]
    return total


def wait_for_engine_stats(after: float, timeout_s: float = 45) -> None:
    """The counters are logged every 30 s, so the first set after the run can take a moment."""
    started = time.time()
    while time.time() - started < timeout_s:
        if any(e.get("msg") == "engine stats" and e["ts"] >= after for e in processor_log(after)):
            return
        time.sleep(5)


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


def stored_flows(since: float, until: float) -> int:
    with psycopg.connect(**stack_conninfo()) as db:
        return db.execute(
            "SELECT count(*) FROM network_flows WHERE source = 'simulator' "
            "AND ingested_at >= to_timestamp(%s) AND ingested_at <= to_timestamp(%s)",
            (since, until),
        ).fetchone()[0]


def latency_view(since: float, until: float) -> dict:
    """The detection_latency view for the same window, to compare with the processor's own numbers."""
    with psycopg.connect(**stack_conninfo()) as db:
        n, negative, p95 = db.execute(
            "SELECT count(*), count(*) FILTER (WHERE latency_s < 0), "
            "percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_s) "
            "FROM detection_latency WHERE created_at >= to_timestamp(%s) AND created_at < to_timestamp(%s)",
            (since, until),
        ).fetchone()
    return {"n": n, "negative": negative, "p95": round(p95, 3) if p95 is not None else None}


def percentile(values: list[float], p: int) -> float | None:
    if len(values) < 2:
        return values[0] if values else None
    return round(statistics.quantiles(values, n=100, method="inclusive")[p - 1], 3)


def latency_stats(values: list[float]) -> dict:
    values = sorted(values)
    percentiles = {f"p{p}": percentile(values, p) for p in (50, 95, 99)}
    return {"n": len(values), **percentiles, "max": values[-1] if values else None}


def lag_growth(rows: list[dict], group: str) -> float | None:
    """Slope of the lag in messages per second over the window; about 0 when the group keeps up."""
    times = [r["t"] for r in rows if r["group"] == group]
    lags = [r["lag"] for r in rows if r["group"] == group]
    if len(times) < 3:
        return None
    return round(statistics.linear_regression(times, lags).slope, 1)


def container_usage(stats_rows: list[dict]) -> dict:
    usage = {}
    for name in sorted({r["container"] for r in stats_rows}):
        cpu = [r["cpu_pct"] for r in stats_rows if r["container"] == name]
        mem = [r["mem_mib"] for r in stats_rows if r["container"] == name]
        usage[name] = {
            "cpu_avg_pct": round(statistics.fmean(cpu), 1),
            "cpu_max_pct": max(cpu),
            "mem_max_mib": round(max(mem)),
        }
    return usage


def summarize(rate: int, run: tuple[float, float], window: tuple[float, float], sampler: Sampler, sent: int) -> dict:
    """run = from the first to the last generated flow, window = run without the warm-up."""
    start, end = window
    lag_rows = [r for r in sampler.lag_rows if start <= r["t"] <= end]
    log = processor_log(run[0] - 35)  # from the last counters before the run
    detections = [e for e in log if e.get("msg") == "detection" and start <= e["ts"] < end]
    stored = stored_flows(run[0] - 1, run[1] + 1)
    return {
        "rate": rate,
        "run": run,
        "window": window,
        "achieved_rate": round(sent / (run[1] - run[0])),
        "sent": sent,
        "stored": stored,
        "lost": sent - stored,
        "late_flows": late_flows(log, *run),
        "max_lag": {g: max((r["lag"] for r in lag_rows if r["group"] == g), default=None) for g in GROUPS},
        "lag_growth_per_s": {g: lag_growth(lag_rows, g) for g in GROUPS},
        "latency_s": latency_stats([d["latency_s"] for d in detections]),
        "latency_by_type": {
            kind: latency_stats([d["latency_s"] for d in detections if d["type"] == kind])
            for kind in sorted({d["type"] for d in detections})
        },
        "latency_view": latency_view(start, end),
        "containers": container_usage([r for r in sampler.stats_rows if start <= r["t"] <= end]),
    }


def run_level(rate: int, warmup: int, measure: int, generators: int, out: Path) -> dict:
    print(f"{rate} flows/s: {warmup} s warm-up + {measure} s measurement", flush=True)
    sampler = Sampler()
    sampler.start()
    generator_logs = run_generators(rate, warmup + measure, generators)
    starts = [e["ts"] for logs in generator_logs for e in logs if e.get("msg") == "load generator started"]
    ends = [e for logs in generator_logs for e in logs if e.get("msg") == "load generator finished"]
    if not starts or len(ends) < generators:
        raise RuntimeError(f"the load generator didn't run at {rate} flows/s: {generator_logs}")
    catch_up_s = wait_until_caught_up(sampler, timeout_s=180)
    sampler.stop.set()
    sampler.join()
    run_end = max(e["ts"] for e in ends)
    wait_for_engine_stats(after=run_end)

    run, window = (min(starts), run_end), (max(starts) + warmup, min(e["ts"] for e in ends))
    summary = summarize(rate, run, window, sampler, sent=sum(e["sent"] for e in ends))
    summary["catch_up_s"] = catch_up_s
    summary["missed_samples"] = sampler.missed_samples
    for name, rows in (("lag", sampler.lag_rows), ("docker_stats", sampler.stats_rows)):
        if rows:
            with open(out / f"{name}_{rate}.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    return summary


def conditions(args: argparse.Namespace) -> dict:
    """Spec 14: every result is recorded together with the machine and the configuration."""
    docker_info = subprocess.run(["docker", "info", "--format", "{{json .}}"], capture_output=True, text=True).stdout
    info = json.loads(docker_info)
    processors = subprocess.run([*COMPOSE, "ps", "-q", "processor"], cwd=ROOT, capture_output=True, text=True).stdout
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout
    return {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": commit.strip(),
        "host": f"{platform.system()} {platform.release()}, {os.cpu_count()} logical CPUs, {platform.processor()}",
        "docker": f"{info['ServerVersion']}, {info['NCPU']} CPUs and {info['MemTotal'] / 2**30:.1f} GiB for Docker",
        "processor_instances": len(processors.split()),
        "partitions": topics.PARTITIONS,
        "detection_config_sha1": hashlib.sha1((ROOT / "config/detection.yaml").read_bytes()).hexdigest()[:12],
        "warmup_s": args.warmup,
        "measure_s": args.measure,
        "generators": args.generators,
    }


def num(value) -> str:
    return "-" if value is None else f"{value:,}"


def print_tables(results: list[dict]) -> None:
    print("\n| Rate | Achieved | Sent | Stored | Lost | Late | Max lag processor / persister | Lag growth msg/s |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        lag = " / ".join(num(r["max_lag"][g]) for g in GROUPS)
        growth = " / ".join(num(r["lag_growth_per_s"][g]) for g in GROUPS)
        row = [num(r[k]) for k in ("rate", "achieved_rate", "sent", "stored", "lost", "late_flows")]
        print(f"| {' | '.join(row)} | {lag} | {growth} |")

    print("\n| Rate | Type | Detections | Latency p50 / p95 / p99 / max (s) |")
    print("|---|---|---|---|")
    for r in results:
        for kind, s in [("all", r["latency_s"]), *r["latency_by_type"].items()]:
            latency = " / ".join(num(s[k]) for k in ("p50", "p95", "p99", "max"))
            print(f"| {num(r['rate'])} | {kind} | {s['n']} | {latency} |")

    print("\n| Rate | Processor CPU avg / max | Persister CPU avg / max | DB CPU avg / max | Caught up after |")
    print("|---|---|---|---|---|")
    for r in results:
        cpu = []
        for service in ("processor", "persister", "db"):
            usage = [u for name, u in r["containers"].items() if f"-{service}-" in name]
            cpu.append(f"{usage[0]['cpu_avg_pct']} / {usage[0]['cpu_max_pct']} %" if usage else "-")
        print(f"| {num(r['rate'])} | {' | '.join(cpu)} | {num(r['catch_up_s'])} s |")


def main() -> None:
    parser = argparse.ArgumentParser(description="Performance baseline against the running stack (PT-01, PT-02).")
    parser.add_argument("--rates", type=int, nargs="+", default=[100, 1000, 5000])
    parser.add_argument("--warmup", type=int, default=60, help="seconds of load before measuring")
    parser.add_argument("--measure", type=int, default=300, help="seconds measured at every rate")
    parser.add_argument("--generators", type=int, default=1, help="load generator containers, the rate is split")
    args = parser.parse_args()

    out = ROOT / "results" / "perf" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    report = {"conditions": conditions(args), "results": []}
    for rate in args.rates:
        report["results"].append(run_level(rate, args.warmup, args.measure, args.generators, out))
        (out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_tables(report["results"])
    print(f"\nResults: {out}")


if __name__ == "__main__":
    main()
