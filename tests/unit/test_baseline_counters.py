"""Processor counters in the performance baseline (PT-01, PT-02): read after the processor caught up."""

import importlib.util
import pathlib
import sys

_PATH = pathlib.Path(__file__).resolve().parents[1] / "performance" / "baseline.py"
_spec = importlib.util.spec_from_file_location("performance_baseline", _PATH)
baseline = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = baseline
_spec.loader.exec_module(baseline)

RUN_START, RUN_END, CAUGHT_UP = 1000.0, 1360.0, 1420.0


def stats(ts, flows, late):
    return {"instance": "processor-1", "msg": "engine stats", "ts": ts, "flows": flows, "late_flows": late}


def test_counters_are_read_after_the_catch_up():
    """Daniyar's case from the #71 review: at the end of the load the processor is 57,080 flows behind, so the
    first stats line after the load is not the whole run."""
    log = [
        stats(990, 10_000, 500),  # before the run
        stats(1370, 10_000 + 1_734_000, 500 + 80_000),  # right after the load, still behind
        stats(1430, 10_000 + 1_791_000, 500 + 84_348),  # after the catch-up
    ]
    assert baseline.counter_growth(log, "flows", RUN_START, CAUGHT_UP) == 1_791_000
    assert baseline.counter_growth(log, "late_flows", RUN_START, CAUGHT_UP) == 84_348


def test_no_counters_after_the_catch_up():
    log = [stats(990, 10_000, 0), stats(1370, 20_000, 0)]
    assert baseline.counter_growth(log, "flows", RUN_START, CAUGHT_UP) is None


def test_processor_started_during_warm_up_counts_from_zero():
    log = [{"instance": "processor-1", "msg": "processor started", "ts": 995}, stats(1430, 5_000, 3)]
    assert baseline.counter_growth(log, "flows", RUN_START, CAUGHT_UP) == 5_000
