"""NetGuard detection engine (owner: Member 2): windows, rules, z-score method, severity, alert policy.

Design: Docs/ArchitectureDocument/detection/README.md
"""

from .config import ConfigError, DetectionConfig, load_config, parse_config
from .engine import DetectionEngine

__all__ = ["ConfigError", "DetectionConfig", "DetectionEngine", "load_config", "parse_config"]
