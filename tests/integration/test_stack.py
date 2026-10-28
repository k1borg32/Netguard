"""Smoke tests against the full running stack (`make up`, then `make test-stack`)."""

import json
import os
import time
import urllib.request

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.stack]
API = os.getenv("API_URL", "http://localhost:8000")


def _get(path):
    with urllib.request.urlopen(API + path, timeout=5) as r:
        return json.loads(r.read())


def test_api_healthy():
    """IT-01: the API is up and reaches the database."""
    assert _get("/health") == {"status": "ok", "db": "ok"}


def test_port_scan_reaches_api():
    """IT-02: simulator -> broker -> processor -> broker -> persister -> DB -> API."""
    from simulator import port_scan_flow

    from netguard_common import topics
    from netguard_common.broker import encode, make_producer

    p = make_producer()
    now = time.time()
    attacker = f"10.99.{int(now) % 250}.{int(now * 10) % 250}"
    for port in range(1, 301):
        f = port_scan_flow(now, attacker, "10.1.0.1")
        f["dst_port"] = port
        p.produce(topics.FLOWS_RAW, key=attacker, value=encode(f))
    p.flush(10)

    deadline = time.time() + 40
    while time.time() < deadline:
        if any(d["src_ip"] == attacker for d in _get("/api/v1/detections?limit=200")["items"]):
            return
        time.sleep(2)
    pytest.fail(f"no detection for {attacker} within 40 s")
