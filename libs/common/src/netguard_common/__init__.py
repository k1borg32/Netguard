"""Shared NetGuard code. Every service imports from here so conventions stay identical."""

from netguard_common import topics
from netguard_common.log import get_logger, new_trace_id, setup_logging, trace_context
from netguard_common.messages import (
    SchemaError,
    detection_id,
    flow_id_for,
    validate_detection,
    validate_flow,
    validate_manifest,
)

__all__ = [
    "SchemaError",
    "detection_id",
    "flow_id_for",
    "get_logger",
    "new_trace_id",
    "setup_logging",
    "topics",
    "trace_context",
    "validate_detection",
    "validate_flow",
    "validate_manifest",
]
