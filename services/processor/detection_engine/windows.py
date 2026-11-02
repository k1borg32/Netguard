"""Tumbling time windows over flow time (F05). Pure logic, unit-testable without a broker.

A window [start, start + size) belongs to one key (a source IP, or a target IP for the DDoS-like check) and holds
the per-window features from spec section 8.

Windows use flow time (`ts_start`), not wall-clock time, so a replayed PCAP is windowed like live traffic. Every key
has its own event clock: the newest `ts_start` seen for it, moved forward by the wall-clock time since its last flow
(so the last window of a source that went quiet still closes). One clock per key and not one per instance, because
all flows of one source come in order from one partition, while different partitions can be far apart in flow time
during a fast import. A window closes once its key's clock passes end + grace. A flow for a window that has already
closed is late: it is counted and dropped.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

MAX_TRACE_IDS = 20  # detection.v1.json allows 50


@dataclass
class _Evidence:
    first_ingested_at: float = float("inf")
    last_ingested_at: float = 0.0
    trace_ids: list[str] = field(default_factory=list)
    # severity rank already sent per finding, so a detection is only sent again when it escalates
    emitted: dict[tuple, int] = field(default_factory=dict)
    dirty: bool = False

    def _touch(self, flow: dict) -> None:
        self.first_ingested_at = min(self.first_ingested_at, flow["ingested_at"])
        self.last_ingested_at = max(self.last_ingested_at, flow["ingested_at"])
        if len(self.trace_ids) < MAX_TRACE_IDS:
            self.trace_ids.append(flow["trace_id"])
        self.dirty = True


@dataclass
class SourceWindow(_Evidence):
    """Features of one source in one window."""

    flows: int = 0
    packets: int = 0
    bytes: int = 0
    dst_ports: set[int] = field(default_factory=set)
    dst_ips: set[str] = field(default_factory=set)
    conns_per_dst: Counter[str] = field(default_factory=Counter)
    packets_per_dst: Counter[str] = field(default_factory=Counter)
    attempts_per_service: Counter[tuple[str, int]] = field(default_factory=Counter)

    def add(self, flow: dict, login_services: frozenset[int]) -> None:
        dst, port = flow["dst_ip"], flow["dst_port"]
        self.flows += 1
        self.packets += flow["packets"]
        self.bytes += flow["bytes"]
        self.dst_ports.add(port)
        self.dst_ips.add(dst)
        self.conns_per_dst[dst] += 1
        self.packets_per_dst[dst] += flow["packets"]
        if port in login_services:
            self.attempts_per_service[(dst, port)] += 1
        self._touch(flow)


@dataclass
class TargetWindow(_Evidence):
    """Traffic towards one target in one window, from every source this instance sees (DDoS-like check)."""

    flows: int = 0
    packets: int = 0
    conns_per_src: Counter[str] = field(default_factory=Counter)

    def add(self, flow: dict) -> None:
        self.flows += 1
        self.packets += flow["packets"]
        self.conns_per_src[flow["src_ip"]] += 1
        self._touch(flow)


@dataclass
class _Clock:
    max_ts: float
    wall: float  # wall-clock time of the key's last flow

    def now(self, wall_now: float) -> float:
        return self.max_ts + max(0.0, wall_now - self.wall)


W = TypeVar("W", bound=_Evidence)


class TumblingWindows(Generic[W]):
    """Windows of one size, keyed by (key, window_start)."""

    def __init__(self, size_s: int, grace_s: float, factory: Callable[[], W]):
        self.size_s = size_s
        self.grace_s = grace_s
        self._factory = factory
        self.windows: dict[tuple[str, float], W] = {}
        self._clocks: dict[str, _Clock] = {}
        self.late_flows = 0

    def window_start(self, ts: float) -> float:
        return ts - (ts % self.size_s)

    def _is_closed(self, start: float, event_now: float) -> bool:
        return start + self.size_s + self.grace_s <= event_now

    def get(self, key: str, ts: float, wall_now: float) -> W | None:
        """The open window of `key` for flow time `ts`, created on first use; None for a late flow."""
        start = self.window_start(ts)
        clock = self._clocks.get(key)
        if clock is None:
            clock = self._clocks[key] = _Clock(ts, wall_now)
        elif self._is_closed(start, clock.now(wall_now)):
            self.late_flows += 1
            return None
        clock.max_ts = max(clock.max_ts, ts)
        clock.wall = wall_now
        w = self.windows.get((key, start))
        if w is None:
            w = self.windows[(key, start)] = self._factory()
        return w

    def dirty(self) -> list[tuple[str, float, W]]:
        """Windows that got flows since the last call, for early evaluation before they close."""
        out = [(k, s, w) for (k, s), w in self.windows.items() if w.dirty]
        for _, _, w in out:
            w.dirty = False
        return out

    def pop_closed(self, wall_now: float) -> list[tuple[str, float, W]]:
        """Remove and return the windows whose key clock has passed end + grace, oldest first."""
        closed = sorted(
            (k for k in self.windows if self._is_closed(k[1], self._clocks[k[0]].now(wall_now))),
            key=lambda k: k[1],
        )
        out = [(key, start, self.windows.pop((key, start))) for key, start in closed]
        if out:
            # forget clocks of keys without open windows that have been quiet for a while
            open_keys = {k for k, _ in self.windows}
            idle_s = max(60.0, 10 * self.size_s)
            for key in [k for k, c in self._clocks.items() if k not in open_keys and wall_now - c.wall > idle_s]:
                del self._clocks[key]
        return out
