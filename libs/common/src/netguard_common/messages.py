"""Message validation and deterministic IDs.

Schemas live in netguard_common/schemas/*.json and are the single source of truth
for message formats. Change a schema -> bump schema_version -> tell the team.
"""

from __future__ import annotations

import json
import uuid
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

# Fixed namespace so every service generates identical IDs for identical inputs.
NETGUARD_NS = uuid.UUID("6f1d2c1e-5b0a-4f3e-9d7a-0e7c1b2a3c4d")


class SchemaError(ValueError):
    pass


@cache
def _validator(name: str) -> Draft202012Validator:
    raw = resources.files("netguard_common").joinpath(f"schemas/{name}").read_text()
    schema = json.loads(raw)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate(name: str, msg: dict[str, Any]) -> dict[str, Any]:
    errors = sorted(_validator(name).iter_errors(msg), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        path = ".".join(str(p) for p in e.path) or "<root>"
        raise SchemaError(f"{name}: {path}: {e.message}")
    return msg


def validate_flow(msg: dict[str, Any]) -> dict[str, Any]:
    return _validate("flow.v1.json", msg)


def validate_detection(msg: dict[str, Any]) -> dict[str, Any]:
    return _validate("detection.v1.json", msg)


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Ground-truth manifest written next to a labelled dataset (test plan 3.6). Not a broker message."""
    _validate("manifest.v1.json", manifest)
    ids = [e["episode_id"] for e in manifest["episodes"]]
    if len(ids) != len(set(ids)):
        raise SchemaError("manifest.v1.json: episodes: episode_id must be unique")
    for i, e in enumerate(manifest["episodes"]):
        if e["end"] < e["start"]:
            raise SchemaError(f"manifest.v1.json: episodes.{i}: end is before start")
    return manifest


def flow_id_for(source_file: str, record_index: int) -> str:
    """Deterministic flow ID for imported data: re-importing the same file gives the same IDs."""
    return str(uuid.uuid5(NETGUARD_NS, f"{source_file}#{record_index}"))


def detection_id(
    det_type: str,
    method: str,
    src_ip: str | None,
    dst_ip: str | None,
    window_start: float,
    window_size_s: int,
) -> str:
    """Same detection seen twice (duplicate/redelivered messages) -> same ID -> DB upsert, no duplicate alert."""
    key = f"{det_type}|{method}|{src_ip}|{dst_ip}|{window_start:.3f}|{window_size_s}"
    return str(uuid.uuid5(NETGUARD_NS, key))
