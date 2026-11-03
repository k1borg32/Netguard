"""Matching rules of the detection quality evaluation (test plan 3.6), used for DQ-01 to DQ-03."""

import importlib.util
import pathlib
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parents[1] / "quality" / "evaluate.py"
_spec = importlib.util.spec_from_file_location("quality_evaluate", _PATH)
evaluate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = evaluate  # dataclasses look their module up there
_spec.loader.exec_module(evaluate)
Detection = evaluate.Detection

T0 = 1_499_000_000.0
SCAN = {"episode_id": "port_scan-001", "class": "port_scan", "attackers": ["172.16.0.1"], "targets": ["192.168.10.50"],
        "start": T0, "end": T0 + 60}  # fmt: skip
DDOS = {"episode_id": "dos-001", "class": "dos", "attackers": ["172.16.0.0/24"], "targets": ["192.168.10.50"],
        "start": T0 + 600, "end": T0 + 900}  # fmt: skip


def scan_detection(start=T0 + 10, src="172.16.0.1", kind="port_scan", size=10):
    return Detection(kind, src, "192.168.10.50", start, start + size)


def test_detection_of_the_episode_matches():
    result = evaluate.evaluate([scan_detection()], [SCAN], hours=1)

    assert result["per_class"]["port_scan"] == {
        "detections": 1, "episodes": 1, "precision": 1.0, "recall": 1.0, "f1": 1.0,
    }  # fmt: skip
    assert result["false_alarms"] == 0


@pytest.mark.parametrize(("start", "matches"), [(T0 + 69, True), (T0 + 71, False), (T0 - 19, True), (T0 - 21, False)])
def test_window_may_be_one_window_off(start, matches):
    """The episode ends at T0 + 60, the window is 10 s long."""
    result = evaluate.evaluate([scan_detection(start=start)], [SCAN], hours=1)

    assert result["per_class"]["port_scan"]["recall"] == (1.0 if matches else 0.0)


def test_other_source_is_a_false_alarm_and_the_episode_is_missed():
    result = evaluate.evaluate([scan_detection(src="10.0.0.9")], [SCAN], hours=2)

    assert result["per_class"]["port_scan"]["precision"] == 0.0
    assert result["per_class"]["port_scan"]["recall"] == 0.0
    assert result["false_alarms"] == 1 and result["false_alarms_per_hour"] == 0.5
    assert result["confusion"] == {"port_scan": {"missed": 1}, "normal": {"port_scan": 1}}


def test_ddos_without_source_matches_by_target_and_attackers_can_be_a_network():
    from_network = Detection("dos", "172.16.0.77", "192.168.10.50", T0 + 700, T0 + 701)
    without_source = Detection("dos", None, "192.168.10.50", T0 + 800, T0 + 801)

    result = evaluate.evaluate([from_network, without_source], [DDOS], hours=1)

    assert result["per_class"]["dos"]["precision"] == 1.0
    assert result["per_class"]["dos"]["recall"] == 1.0


def test_wrong_class_counts_against_both_classes():
    """DoS detected during the port scan: false positive for dos, the port scan is missed."""
    result = evaluate.evaluate([scan_detection(kind="dos", size=1)], [SCAN], hours=1)

    assert result["per_class"]["dos"] == {"detections": 1, "episodes": 0, "precision": 0.0, "recall": None, "f1": None}
    assert result["per_class"]["port_scan"]["recall"] == 0.0
    assert result["confusion"] == {"port_scan": {"dos": 1}}
    assert result["false_alarms"] == 0  # it hit the episode, just with the wrong class


def test_unknown_on_an_episode_is_reported_as_not_classified():
    result = evaluate.evaluate([scan_detection(kind="unknown", size=60)], [SCAN], hours=1)

    assert result["unclassified_episodes"] == 1
    assert result["per_class"]["port_scan"]["recall"] == 0.0


def test_several_detections_of_one_episode_count_once_for_recall():
    detections = [scan_detection(start=T0 + s) for s in (0, 10, 20, 30)]

    result = evaluate.evaluate(detections, [SCAN, DDOS], hours=1)

    assert result["per_class"]["port_scan"]["recall"] == 1.0
    assert result["detections_per_matched_episode"] == {"avg": 4, "max": 4}
    assert result["per_class"]["dos"]["f1"] == 0.0  # episode without any detection
    assert result["macro_f1"] == 0.5
