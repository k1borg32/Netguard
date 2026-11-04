"""Replay pacing for old datasets (owner: Member 1).

The processor closes its time windows by the wall clock, so flows with timestamps from
2017 would all look old and every window would be closed after each batch (risk R12).
The Replayer rebases the timestamps to the present and sleeps between flows, so the data
arrives like live traffic. Original gaps are kept, divided by `speed`; `max_gap_s` caps
long idle periods (in seconds of the original data).

speed=1 keeps real time: rates stay realistic and the detection thresholds apply as they
are. speed>1 compresses time: all rates multiply by `speed`, use it for quick checks only.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class Replayer:
    def __init__(
        self,
        speed: float = 1.0,
        max_gap_s: float | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if speed <= 0:
            raise ValueError("REPLAY_SPEED must be greater than 0")
        if max_gap_s is not None and max_gap_s < 0:
            raise ValueError("REPLAY_MAX_GAP_S must not be negative")
        self.speed = speed
        self.max_gap_s = max_gap_s
        self._clock = clock
        self._sleep = sleep
        self._prev: float | None = None
        self._start_wall = 0.0
        self._elapsed = 0.0

    def rebase(self, ts: float) -> float:
        """Wait until the flow is due, then return its new (present-time) ts_start."""
        now = self._clock()
        if self._prev is None:
            self._start_wall = now
            self._prev = ts
        else:
            gap = ts - self._prev
            if gap > 0:  # out-of-order flows get the time of the previous one
                if self.max_gap_s is not None:
                    gap = min(gap, self.max_gap_s)
                self._elapsed += gap / self.speed
                self._prev = ts
        due = self._start_wall + self._elapsed
        wait = due - now
        if wait > 0:
            self._sleep(wait)
        return due
