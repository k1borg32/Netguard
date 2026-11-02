"""Which detections become alerts (F17, detection.yaml `alerts`).

Every detection is stored. An alert is the subset an operator has to look at and acknowledge, so the policy is
there to keep false alarms and repeats down (spec 2: "reduce false alarms"; DQ-02: at most 2 alerts per 10 min of
normal traffic):

1. severity >= `min_severity` (or the stricter value in `min_severity_by_type` for that type);
2. at most one alert per (type, source, destination) per `cooldown_s` of flow time, so a scan that runs over
   six 10 s windows raises one alert, not six;
3. except when the severity goes up: a HIGH detection inside the cooldown of a MEDIUM alert raises a new alert.

The same detection sent again (it escalated inside its window) keeps its alert, and the persister stores at most
one alert per detection. Cooldown state is per processor instance, which is enough because one source is always
handled by the same instance (flows are keyed by src_ip).
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import AlertCfg
from .scoring import SEVERITY_RANK


@dataclass
class _LastAlert:
    at: float  # window start (flow time), so the cooldown of a replayed PCAP follows the capture's own time
    rank: int
    detection_id: str
    wall: float  # wall-clock time, only for forgetting old entries


class AlertPolicy:
    def __init__(self, cfg: AlertCfg):
        self.cfg = cfg
        self._last: dict[tuple[str, str | None, str | None], _LastAlert] = {}

    def decide(self, det: dict, wall_now: float) -> bool:
        """True if detection `det` raises an alert."""
        rank = SEVERITY_RANK[det["severity"]]
        if rank < SEVERITY_RANK[self.cfg.min_for(det["type"])]:
            return False
        key = (det["type"], det["src_ip"], det["dst_ip"])
        at = det["window"]["start"]
        last = self._last.get(key)
        if last is not None and last.detection_id != det["detection_id"]:
            in_cooldown = 0 <= at - last.at < self.cfg.cooldown_s
            if in_cooldown and rank <= last.rank:
                return False
        if last is None or last.detection_id != det["detection_id"] or rank > last.rank:
            self._last[key] = _LastAlert(at=at, rank=rank, detection_id=det["detection_id"], wall=wall_now)
        return True

    def forget_idle(self, wall_before: float) -> None:
        for key in [k for k, v in self._last.items() if v.wall < wall_before]:
            del self._last[key]
