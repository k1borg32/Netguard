"""Detection engine: flows in, detection.v1 messages out. No broker or database here, so it is unit-testable.

    engine = DetectionEngine(load_config("config/detection.yaml"))
    engine.add(flow, wall_now)           # for every flow of a batch
    detections = engine.evaluate(wall_now)  # once per batch

`evaluate` first closes the windows whose time is over (final evaluation, then the history of the statistical
method and the connection profiles learn from them), then evaluates the windows that got new flows. Rules on open
windows fire as soon as the threshold is crossed (NFR02, Conventions 4). If a detection escalates later in the same
window it is sent again with the same detection_id and the higher severity; it is never sent twice at the same
severity.
"""

from __future__ import annotations

from netguard_common import detection_id

from . import rules
from .alerting import AlertPolicy
from .config import DetectionConfig
from .rules import Finding
from .scoring import SEVERITY_RANK, confidence_for, severity_for
from .statistical import ZScoreDetector
from .windows import SourceWindow, TargetWindow, TumblingWindows, _Evidence

MAX_PROFILE_HOSTS = 5_000  # per source; a sweeping source must not grow its profile without limit
FORGET_EVERY_S = 60.0


class DetectionEngine:
    def __init__(self, cfg: DetectionConfig):
        self.cfg = cfg
        self.sources = {s: TumblingWindows(s, cfg.grace_s, SourceWindow) for s in cfg.windows_s}
        self.targets = TumblingWindows(cfg.dos.window_s, cfg.grace_s, TargetWindow)
        self.zscore = ZScoreDetector(cfg.statistical)
        self.alerts = AlertPolicy(cfg.alerts)
        # src -> dst_ip -> end of the last window in which src contacted it (suspicious_pattern profile)
        self.profiles: dict[str, dict[str, float]] = {}
        self._profile_wall: dict[str, float] = {}
        # src -> latest end of a window in which a rule fired (an `unknown` there would only repeat it)
        self.rule_hits: dict[str, float] = {}
        self.flows = 0
        self.bad_flows = 0
        self.late_flows = 0
        self._last_forget = 0.0

    # ---- input ----

    def add(self, flow: dict, wall_now: float) -> bool:
        """Add one flow to every window it belongs to. False if the flow is missing a field the engine needs."""
        try:
            src, dst, ts = flow["src_ip"], flow["dst_ip"], float(flow["ts_start"])
            # check everything the windows read before touching any of them, so a bad flow changes nothing
            if not all(isinstance(flow[k], int | float) for k in ("dst_port", "packets", "bytes", "ingested_at")):
                raise TypeError
            flow["trace_id"]  # noqa: B018
            login = self.cfg.brute_force.services
            late = False
            for store in self.sources.values():
                w = store.get(src, ts, wall_now)
                if w is None:
                    late = True
                else:
                    w.add(flow, login)
            t = self.targets.get(dst, ts, wall_now)
            if t is None:
                late = True
            else:
                t.add(flow)
        except (KeyError, TypeError, ValueError):
            self.bad_flows += 1
            return False
        self.flows += 1
        self.late_flows += late  # late for at least one window; still counted in the windows that were open
        return True

    # ---- evaluation ----

    def evaluate(self, wall_now: float) -> list[dict]:
        out: list[dict] = []
        # ascending window size: the 10 s rules have set rule_hits before the 60 s statistical window closes
        for size, store in self.sources.items():
            for src, start, w in store.pop_closed(wall_now):
                out += self._source_window(size, src, start, w, wall_now, final=True)
        for dst, start, w in self.targets.pop_closed(wall_now):
            out += self._emit(w, start, self.targets.size_s, rules.dos_on_target(self.cfg, dst, w), wall_now)
        for size, store in self.sources.items():
            for src, start, w in store.dirty():
                out += self._source_window(size, src, start, w, wall_now, final=False)
        for dst, start, w in self.targets.dirty():
            out += self._emit(w, start, self.targets.size_s, rules.dos_on_target(self.cfg, dst, w), wall_now)
        if wall_now - self._last_forget >= FORGET_EVERY_S:
            self._forget(wall_now)
        return out

    def _source_window(
        self, size: int, src: str, start: float, w: SourceWindow, wall_now: float, *, final: bool
    ) -> list[dict]:
        c = self.cfg
        found: list[Finding] = []
        if size == c.port_scan.window_s:
            found += rules.port_scan(c, src, w)
        if size == c.dos.window_s:
            found += rules.dos_from_source(c, src, w)
        if size == c.brute_force.window_s:
            found += rules.brute_force(c, src, w)
        if size == c.suspicious_pattern.window_s:
            found += rules.suspicious_pattern(c, src, w, self._known_hosts(src, start))
        if found:
            self.rule_hits[src] = max(self.rule_hits.get(src, float("-inf")), start + size)
        if final and size == c.statistical.window_s:
            # Statistical method on closed windows only: until then a rule may still explain the same traffic,
            # and a known class wins over "the source changed". Anomalous windows are not learned.
            explained = self.rule_hits.get(src, float("-inf")) > start
            stat = [] if explained else self.zscore.evaluate(src, start, w)
            found += stat
            if not explained and not stat:
                self.zscore.learn(src, start, w, wall_now)
        if final and size == c.suspicious_pattern.window_s:
            self._learn_profile(src, start + size, w, wall_now)
        return self._emit(w, start, size, found, wall_now)

    def _emit(self, w: _Evidence, start: float, size: int, found: list[Finding], wall_now: float) -> list[dict]:
        out = []
        for f in found:
            severity = severity_for(f.ratio, self.cfg.severity)
            rank = SEVERITY_RANK[severity]
            key = (f.type, f.method, f.src_ip, f.dst_ip)
            if w.emitted.get(key, -1) >= rank:
                continue
            w.emitted[key] = rank
            det = self._detection(f, severity, w, start, size, wall_now)
            det["alert"] = self.alerts.decide(det, wall_now)
            out.append(det)
        return out

    def _detection(self, f: Finding, severity: str, w: _Evidence, start: float, size: int, now: float) -> dict:
        ratio = f.ratio
        return {
            "schema_version": 1,
            "detection_id": detection_id(f.type, f.method, f.src_ip, f.dst_ip, start, size),
            "trace_ids": list(w.trace_ids),
            "created_at": now,
            "first_ingested_at": w.first_ingested_at,
            "last_ingested_at": w.last_ingested_at,
            "type": f.type,
            "method": f.method,
            "severity": severity,
            "confidence": confidence_for(ratio, f.method, f.type),
            "src_ip": f.src_ip,
            "dst_ip": f.dst_ip,
            "window": {"size_s": size, "start": start, "end": start + size},
            "features": {**f.features, "threshold": f.threshold, "ratio": round(ratio, 3)},
            "explanation": f"{f.explanation} {ratio:.1f}x the threshold -> {severity}.",
        }

    # ---- connection profiles (suspicious_pattern) ----

    def _known_hosts(self, src: str, start: float) -> set[str]:
        horizon = start - self.cfg.suspicious_pattern.profile_window_s
        return {ip for ip, seen in self.profiles.get(src, {}).items() if seen > horizon}

    def _learn_profile(self, src: str, end: float, w: SourceWindow, wall_now: float) -> None:
        profile = self.profiles.setdefault(src, {})
        for ip in w.dst_ips:
            if ip in profile or len(profile) < MAX_PROFILE_HOSTS:
                profile[ip] = end
        horizon = end - self.cfg.suspicious_pattern.profile_window_s
        for ip in [ip for ip, seen in profile.items() if seen <= horizon]:
            del profile[ip]
        self._profile_wall[src] = wall_now

    # ---- housekeeping ----

    def _forget(self, wall_now: float) -> None:
        """Drop per-source state of sources that have been quiet for longer than that state is used."""
        self._last_forget = wall_now
        c = self.cfg
        self.zscore.forget_idle(wall_now - c.statistical.baseline_window_s - c.statistical.window_s)
        self.alerts.forget_idle(wall_now - c.alerts.cooldown_s)
        before = wall_now - c.suspicious_pattern.profile_window_s
        for src in [s for s, t in self._profile_wall.items() if t < before]:
            del self._profile_wall[src]
            self.profiles.pop(src, None)
            self.rule_hits.pop(src, None)

    def stats(self) -> dict[str, int]:
        return {
            "flows": self.flows,
            "bad_flows": self.bad_flows,
            "late_flows": self.late_flows,
            "open_windows": sum(len(s.windows) for s in self.sources.values()) + len(self.targets.windows),
            "tracked_sources": len(self.zscore.baselines),
        }
