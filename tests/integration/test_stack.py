"""Integration tests against the running stack."""

import json
import os
import urllib.request

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.stack]
API = os.getenv("API_URL", "http://localhost:8000")


def _get(path):
    with urllib.request.urlopen(API + path, timeout=5) as r:
        return json.loads(r.read())


def test_api_healthy():
    """IT-01: Verify that the API is running."""
    assert _get("/health/ping")["status"] == "ok"
