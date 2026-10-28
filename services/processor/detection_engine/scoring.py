"""Severity and confidence (spec 9.3, UT-16).

ratio = observed / threshold (z / zscore_threshold for the statistical method), so 1.0 means "just crossed".
Severity is the highest level in detection.yaml `severity` whose value is <= ratio.

Confidence says how sure we are that the class is right, not how bad it is. It grows with the ratio and has a
ceiling per method: a rule checks the exact behaviour of its class, a z-score only says the source changed, and
`unknown` has no class behind it at all. The values are first estimates, checked in the quality tests (DQ-01).
"""

from __future__ import annotations

from .config import SEVERITIES

SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}

# (base, ceiling) per method / type: confidence = min(ceiling, base + 0.1 * ratio)
_CONFIDENCE = {"rule": (0.5, 1.0), "statistical": (0.4, 0.9), "unknown": (0.3, 0.7)}


def severity_for(ratio: float, levels: dict[str, float]) -> str:
    best = SEVERITIES[0]
    for name in SEVERITIES:
        if ratio >= levels[name]:
            best = name
    return best


def confidence_for(ratio: float, method: str, det_type: str) -> float:
    base, ceiling = _CONFIDENCE["unknown" if det_type == "unknown" else method]
    return round(min(ceiling, base + 0.1 * ratio), 3)
