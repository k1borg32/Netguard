"""IT-06: one trace_id followed from the flows to the detection, the API and the service logs (F15, NFR08).

Runs against the full stack (`make up`, then `make test-stack`). The flows come from the test, so the test is the
first component and creates the trace ids (CONVENTIONS 3). The persister doesn't log trace ids yet (a defect in the
test report), that check is marked as expected to fail.
"""

import json
import os
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.stack]

ROOT = Path(__file__).resolve().parents[2]
API = os.getenv("API_URL", "http://localhost:8000")
DETECTION_TIMEOUT_S = 40


def service_log(service: str, since: float) -> list[dict]:
    """JSON log lines of one Compose service since a moment."""
    started = datetime.fromtimestamp(since - 5, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = subprocess.run(
        ["docker", "compose", "logs", "--no-color", "--since", started, service],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    ).stdout
    lines = []
    for line in out.splitlines():
        _, _, text = line.partition("|")  # "processor-1  | {...}"
        try:
            lines.append(json.loads(text))
        except ValueError:
            continue
    return lines


@pytest.fixture(scope="module")
def traced_scan(stack_db):
    """A port scan from a new address, every flow with its own trace_id, and the detection it ends in."""
    from loadgen import port_scan_flow

    from netguard_common import topics
    from netguard_common.broker import encode, make_producer

    started = time.time()
    attacker = f"10.98.{int(started) % 250}.{int(started * 10) % 250}"
    producer = make_producer()
    sent = set()
    for port in range(1, 301):
        flow = port_scan_flow(started, attacker, "10.1.0.1")
        flow["dst_port"] = port
        sent.add(flow["trace_id"])
        producer.produce(topics.FLOWS_RAW, key=attacker, value=encode(flow))
    producer.flush(10)

    deadline = time.time() + DETECTION_TIMEOUT_S
    while time.time() < deadline:
        row = stack_db.execute(
            "SELECT detection_id::text, trace_ids FROM detections WHERE host(src_ip) = %s AND type = 'port_scan'",
            (attacker,),
        ).fetchone()
        if row:
            return {"started": started, "sent": sent, "detection_id": row[0], "trace_ids": row[1]}
        time.sleep(2)
    pytest.fail(f"no port_scan detection for {attacker} within {DETECTION_TIMEOUT_S} s")


def test_detection_keeps_trace_ids_of_its_flows(traced_scan):
    """IT-06: the stored detection carries a sample of the trace ids of the flows behind it."""
    assert traced_scan["trace_ids"], "detection without trace ids"
    assert set(traced_scan["trace_ids"]) <= traced_scan["sent"]


def test_api_returns_the_trace_ids(traced_scan):
    """IT-06: the operator gets the same trace ids from the API (detection details)."""
    with urllib.request.urlopen(f"{API}/api/v1/detections/{traced_scan['detection_id']}", timeout=5) as response:
        details = json.loads(response.read())
    assert details["trace_ids"] == traced_scan["trace_ids"]


def test_processor_logs_the_detection_with_its_trace_id(traced_scan):
    """IT-06: `make trace ID=<trace_id>` finds the processor's detection line."""
    lines = [
        line
        for line in service_log("processor", traced_scan["started"])
        if line.get("msg") == "detection" and line.get("detection_id") == traced_scan["detection_id"]
    ]
    assert lines, "no detection line in the processor log"
    assert all(line["trace_id"] in traced_scan["sent"] for line in lines)


@pytest.mark.xfail(strict=True, reason="the persister logs whole batches without trace ids")
def test_persister_logs_the_trace_id(traced_scan):
    """IT-06: the persister writes a log line with the trace id when it stores the detection."""
    deadline = time.time() + 10
    while time.time() < deadline:
        lines = service_log("persister", traced_scan["started"])
        if any(line.get("trace_id") in traced_scan["trace_ids"] for line in lines):
            return
        time.sleep(2)
    pytest.fail("no persister log line with a trace id of the detection")
