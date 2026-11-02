"""Load and check config/detection.yaml (spec 9.1: parameters configurable, defaults in project config).

The processor refuses to start on a missing or invalid value (UT-17), so a typo never silently disables a rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
DETECTION_TYPES = ("port_scan", "dos", "brute_force", "abnormal_traffic", "suspicious_pattern", "unknown")
ALLOWED_WINDOWS = (1, 10, 60)  # detection.v1.json window.size_s


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class PortScanCfg:
    window_s: int
    unique_dst_ports_threshold: int


@dataclass(frozen=True)
class DosCfg:
    window_s: int
    connections_to_target_threshold: int
    packets_to_target_threshold: int
    ddos_min_sources: int


@dataclass(frozen=True)
class BruteForceCfg:
    window_s: int
    attempts_same_service_threshold: int
    services: frozenset[int]


@dataclass(frozen=True)
class SuspiciousPatternCfg:
    window_s: int
    new_dst_ips_threshold: int
    profile_window_s: int


@dataclass(frozen=True)
class StatisticalCfg:
    method: str
    window_s: int
    baseline_window_s: int
    min_baseline_windows: int
    zscore_threshold: float

    @property
    def history_len(self) -> int:
        return self.baseline_window_s // self.window_s


@dataclass(frozen=True)
class AlertCfg:
    min_severity: str
    min_severity_by_type: dict[str, str]
    cooldown_s: float

    def min_for(self, det_type: str) -> str:
        return self.min_severity_by_type.get(det_type, self.min_severity)


@dataclass(frozen=True)
class DetectionConfig:
    windows_s: tuple[int, ...]
    grace_s: float
    port_scan: PortScanCfg
    dos: DosCfg
    brute_force: BruteForceCfg
    suspicious_pattern: SuspiciousPatternCfg
    statistical: StatisticalCfg
    severity: dict[str, float]
    alerts: AlertCfg


def load_config(path: str) -> DetectionConfig:
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except OSError as e:
        raise ConfigError(f"{path}: cannot read: {e}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: not valid YAML: {e}") from e
    return parse_config(raw)


def _section(raw: Any, path: str) -> dict:
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping")
    return raw


def _num(sec: dict, key: str, path: str, *, integer: bool = False, minimum: float = 0, strict: bool = True):
    if key not in sec:
        raise ConfigError(f"{path}.{key}: missing")
    v = sec[key]
    if isinstance(v, bool) or not isinstance(v, int if integer else (int, float)):
        raise ConfigError(f"{path}.{key}: expected {'an integer' if integer else 'a number'}, got {v!r}")
    if v < minimum or (strict and v == minimum):
        raise ConfigError(f"{path}.{key}: must be {'>' if strict else '>='} {minimum}, got {v}")
    return v


def _window(sec: dict, path: str, windows: tuple[int, ...]) -> int:
    w = _num(sec, "window_s", path, integer=True)
    if w not in windows:
        raise ConfigError(f"{path}.window_s: {w} is not one of windows_s {list(windows)}")
    return w


def _severity_name(v: Any, path: str) -> str:
    if v not in SEVERITIES:
        raise ConfigError(f"{path}: expected one of {list(SEVERITIES)}, got {v!r}")
    return v


def parse_config(raw: Any) -> DetectionConfig:
    root = _section(raw, "<root>")

    windows = root.get("windows_s")
    if not isinstance(windows, list) or not windows or any(w not in ALLOWED_WINDOWS for w in windows):
        raise ConfigError(f"windows_s: expected a non-empty list of {list(ALLOWED_WINDOWS)}, got {windows!r}")
    missing = set(ALLOWED_WINDOWS) - set(windows)
    if missing:
        raise ConfigError(f"windows_s: F05 needs 1, 10 and 60 s windows, missing {sorted(missing)}")
    windows_t = tuple(sorted(set(windows)))
    grace = _num(root, "grace_s", "grace_s", minimum=0, strict=False)

    rules = _section(root.get("rules"), "rules")
    ps = _section(rules.get("port_scan"), "rules.port_scan")
    dos = _section(rules.get("dos"), "rules.dos")
    bf = _section(rules.get("brute_force"), "rules.brute_force")
    sp = _section(rules.get("suspicious_pattern"), "rules.suspicious_pattern")

    services = bf.get("services")
    if (
        not isinstance(services, list)
        or not services
        or any(isinstance(p, bool) or not isinstance(p, int) or not 0 < p <= 65535 for p in services)
    ):
        raise ConfigError(f"rules.brute_force.services: expected a non-empty list of ports, got {services!r}")

    sp_window = _window(sp, "rules.suspicious_pattern", windows_t)
    profile_s = _num(sp, "profile_window_s", "rules.suspicious_pattern", integer=True)
    if profile_s < sp_window:
        raise ConfigError("rules.suspicious_pattern.profile_window_s: must be >= its window_s")

    st = _section(root.get("statistical"), "statistical")
    if st.get("method") != "zscore":
        raise ConfigError(f"statistical.method: only 'zscore' is implemented, got {st.get('method')!r}")
    st_window = _window(st, "statistical", windows_t)
    baseline_s = _num(st, "baseline_window_s", "statistical", integer=True)
    if baseline_s % st_window:
        raise ConfigError("statistical.baseline_window_s: must be a multiple of statistical.window_s")
    min_windows = _num(st, "min_baseline_windows", "statistical", integer=True, minimum=2, strict=False)
    if min_windows > baseline_s // st_window:
        raise ConfigError(
            f"statistical.min_baseline_windows: {min_windows} windows don't fit in baseline_window_s "
            f"({baseline_s // st_window} windows of {st_window} s)"
        )

    sev = _section(root.get("severity"), "severity")
    levels = {}
    for name in SEVERITIES:
        levels[name] = float(_num(sev, name, "severity"))
    if list(levels.values()) != sorted(levels.values()) or len(set(levels.values())) != len(levels):
        raise ConfigError(f"severity: values must increase from LOW to CRITICAL, got {levels}")
    unknown_levels = set(sev) - set(SEVERITIES)
    if unknown_levels:
        raise ConfigError(f"severity: unknown levels {sorted(unknown_levels)}")

    al = _section(root.get("alerts"), "alerts")
    by_type = _section(al.get("min_severity_by_type") or {}, "alerts.min_severity_by_type")
    for t, s in by_type.items():
        if t not in DETECTION_TYPES:
            raise ConfigError(f"alerts.min_severity_by_type: unknown detection type {t!r}")
        _severity_name(s, f"alerts.min_severity_by_type.{t}")

    return DetectionConfig(
        windows_s=windows_t,
        grace_s=float(grace),
        port_scan=PortScanCfg(
            window_s=_window(ps, "rules.port_scan", windows_t),
            unique_dst_ports_threshold=_num(ps, "unique_dst_ports_threshold", "rules.port_scan", integer=True),
        ),
        dos=DosCfg(
            window_s=_window(dos, "rules.dos", windows_t),
            connections_to_target_threshold=_num(dos, "connections_to_target_threshold", "rules.dos", integer=True),
            packets_to_target_threshold=_num(dos, "packets_to_target_threshold", "rules.dos", integer=True),
            ddos_min_sources=_num(dos, "ddos_min_sources", "rules.dos", integer=True, minimum=2, strict=False),
        ),
        brute_force=BruteForceCfg(
            window_s=_window(bf, "rules.brute_force", windows_t),
            attempts_same_service_threshold=_num(
                bf, "attempts_same_service_threshold", "rules.brute_force", integer=True
            ),
            services=frozenset(services),
        ),
        suspicious_pattern=SuspiciousPatternCfg(
            window_s=sp_window,
            new_dst_ips_threshold=_num(sp, "new_dst_ips_threshold", "rules.suspicious_pattern", integer=True),
            profile_window_s=profile_s,
        ),
        statistical=StatisticalCfg(
            method="zscore",
            window_s=st_window,
            baseline_window_s=baseline_s,
            min_baseline_windows=min_windows,
            zscore_threshold=float(_num(st, "zscore_threshold", "statistical")),
        ),
        severity=levels,
        alerts=AlertCfg(
            min_severity=_severity_name(al.get("min_severity"), "alerts.min_severity"),
            min_severity_by_type=dict(by_type),
            cooldown_s=float(_num(al, "cooldown_s", "alerts", minimum=0, strict=False)),
        ),
    )
