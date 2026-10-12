"""Structured JSON logging with a trace_id on every line (NFR08, F15).

Usage in any service:

    from netguard_common import setup_logging, get_logger, trace_context
    setup_logging("processor")
    log = get_logger(__name__)

    with trace_context(flow["trace_id"]):
        log.info("flow accepted", extra={"src_ip": flow["src_ip"]})

Every line is one JSON object, so `docker compose logs | grep <trace_id>`
shows the full path of one event through the system.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_service_name = "unknown"

# Attributes present on every LogRecord; anything else came from `extra=` and is emitted.
_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


def new_trace_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def trace_context(trace_id: str | None) -> Iterator[None]:
    token = _trace_id.set(trace_id)
    try:
        yield
    finally:
        _trace_id.reset(token)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": round(record.created, 3),
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "level": record.levelname,
            "service": _service_name,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": _trace_id.get(),
        }
        for k, v in record.__dict__.items():
            if k not in _RESERVED and not k.startswith("_"):
                out[k] = v
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup_logging(service: str, level: str | None = None) -> None:
    global _service_name
    _service_name = service
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel((level or os.getenv("LOG_LEVEL", "INFO")).upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
