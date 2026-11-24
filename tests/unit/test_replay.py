"""Unit tests for the replay pacing (services/importer/replay.py), risk R12.

Test plan: UT-21.
"""

import importlib
import pathlib
import sys

import pytest

BASE = pathlib.Path(__file__).resolve().parents[2] / "services" / "importer"
sys.path.insert(0, str(BASE))
replay = importlib.import_module("replay")


class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def _replayer(**kw):
    t = FakeTime()
    return replay.Replayer(clock=t.clock, sleep=t.sleep, **kw), t


def test_real_time_keeps_original_gaps():
    r, t = _replayer(speed=1)
    assert [r.rebase(ts) for ts in (100.0, 102.0, 102.5)] == [1000.0, 1002.0, 1002.5]
    assert t.slept == [2.0, 0.5]


def test_speed_divides_gaps():
    r, t = _replayer(speed=10)
    r.rebase(0.0)
    assert r.rebase(20.0) == 1002.0


def test_max_gap_caps_idle_periods():
    r, t = _replayer(speed=1, max_gap_s=5)
    r.rebase(0.0)
    assert r.rebase(1000.0) == 1005.0


def test_out_of_order_flow_does_not_go_back():
    r, t = _replayer(speed=1)
    r.rebase(100.0)
    r.rebase(105.0)
    assert r.rebase(103.0) == 1005.0


def test_rebased_time_is_in_the_present_not_2017():
    r, t = _replayer(speed=1)
    assert r.rebase(1499428800.0) == 1000.0  # a July 2017 timestamp


@pytest.mark.parametrize("speed", [0, -1])
def test_bad_speed_rejected(speed):
    with pytest.raises(ValueError):
        replay.Replayer(speed=speed)
