"""Second detection method (F07, spec 9.2): per-source z-score against the source's own recent history.

For every source the method keeps the features of its last `baseline_window_s / window_s` closed windows (a quiet
window counts as zero). A new window is scored per feature as z = (value - mean) / std:

* volume features (flows, packets, bytes) above the threshold -> `abnormal_traffic`
* only connection-structure features (unique ports / hosts) above it -> `unknown` (anomalous, no known class)

The engine runs this on closed windows only and skips it when a rule already fired for the source in that period.
No score before `min_baseline_windows` windows of history. Anomalous windows are not added to the history, so an
attack does not become the new normal. A source quiet for longer than the whole history starts
over, because comparing with a history of zeros would flag any traffic at all.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from .config import StatisticalCfg
from .rules import Finding
from .windows import SourceWindow

VOLUME = ("flows", "packets", "bytes")
STRUCTURE = ("unique_dst_ports", "unique_dst_ips")


def window_features(w: SourceWindow) -> dict[str, float]:
    return {
        "flows": w.flows,
        "packets": w.packets,
        "bytes": w.bytes,
        "unique_dst_ports": len(w.dst_ports),
        "unique_dst_ips": len(w.dst_ips),
    }


@dataclass
class Score:
    feature: str
    value: float
    mean: float
    std: float
    z: float


class SourceBaseline:
    def __init__(self, maxlen: int):
        self.history: deque[dict[str, float]] = deque(maxlen=maxlen)
        self.last_start: float | None = None
        self.wall = 0.0  # wall-clock time of the last update, for forgetting quiet sources

    def _history_at(self, start: float, size_s: int, keys: dict[str, float]) -> list[dict[str, float]]:
        """History as seen from the window at `start`: quiet windows in between count as zeros."""
        hist = list(self.history)
        if self.last_start is None:
            return hist
        gap = round((start - self.last_start) / size_s) - 1
        if gap >= self.history.maxlen:
            return []
        hist += [dict.fromkeys(keys, 0.0)] * max(0, gap)
        return hist[-self.history.maxlen :]

    def observe(self, start: float, size_s: int, values: dict[str, float]) -> None:
        hist = self._history_at(start, size_s, values)
        self.history.clear()
        self.history.extend(hist)
        self.history.append(values)
        self.last_start = start

    def scores(self, values: dict[str, float], start: float, size_s: int) -> tuple[list[Score], int]:
        hist = self._history_at(start, size_s, values)
        out = []
        for feature, value in values.items():
            col = [h[feature] for h in hist]
            mean = sum(col) / len(col) if col else 0.0
            std = math.sqrt(sum((x - mean) ** 2 for x in col) / len(col)) if col else 0.0
            # floor: a perfectly steady history (std 0) must not turn one extra flow into an infinite z;
            # sqrt(mean) is the spread of a count that fluctuates randomly (Poisson)
            std = max(std, math.sqrt(mean), 0.1 * mean, 1.0)
            out.append(Score(feature, value, mean, std, (value - mean) / std))
        return out, len(hist)


class ZScoreDetector:
    def __init__(self, cfg: StatisticalCfg):
        self.cfg = cfg
        self.baselines: dict[str, SourceBaseline] = {}

    def evaluate(self, src: str, start: float, w: SourceWindow) -> list[Finding]:
        b = self.baselines.get(src)
        if b is None:
            return []
        values = window_features(w)
        scores, n_hist = b.scores(values, start, self.cfg.window_s)
        if n_hist < self.cfg.min_baseline_windows:
            return []
        thr = self.cfg.zscore_threshold
        by_name = {s.feature: s for s in scores}
        volume = max((by_name[f] for f in VOLUME), key=lambda s: s.z)
        structure = max((by_name[f] for f in STRUCTURE), key=lambda s: s.z)
        if volume.z >= thr:
            det_type, top = "abnormal_traffic", volume
        elif structure.z >= thr:
            det_type, top = "unknown", structure
        else:
            return []
        features: dict[str, float | int | str | bool] = {f: int(v) for f, v in values.items()}
        features.update(
            feature=top.feature,
            baseline_mean=round(top.mean, 3),
            baseline_std=round(top.std, 3),
            zscore=round(top.z, 3),
            baseline_windows=n_hist,
        )
        return [
            Finding(
                type=det_type,
                method="statistical",
                src_ip=src,
                dst_ip=next(iter(w.dst_ips)) if len(w.dst_ips) == 1 else None,
                observed=top.z,
                threshold=thr,
                explanation=(
                    f"{src} had {int(top.value)} {top.feature.replace('_', ' ')} in {self.cfg.window_s} s; "
                    f"its last {n_hist} windows averaged {top.mean:.1f} (std {top.std:.1f}), "
                    f"z-score {top.z:.1f} (threshold {thr})."
                ),
                features=features,
            )
        ]

    def learn(self, src: str, start: float, w: SourceWindow, wall_now: float) -> None:
        b = self.baselines.get(src)
        if b is None:
            b = self.baselines[src] = SourceBaseline(self.cfg.history_len)
        b.observe(start, self.cfg.window_s, window_features(w))
        b.wall = wall_now

    def forget_idle(self, wall_before: float) -> None:
        """Drop sources not seen since `wall_before` (wall clock); they would start over anyway."""
        for src in [s for s, b in self.baselines.items() if b.wall < wall_before]:
            del self.baselines[src]
