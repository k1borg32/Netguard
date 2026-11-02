"""Unit tests for the ground-truth manifest generator (services/importer/make_manifest.py).

Test plan: UT-22.
"""

import csv
import importlib
import json
import pathlib
import sys

import pytest

BASE = pathlib.Path(__file__).resolve().parents[2] / "services" / "importer"
sys.path.insert(0, str(BASE))
make_manifest = importlib.import_module("make_manifest")


def _csv(path, rows, header=("ts_start", "src_ip", "dst_ip", "dst_port", "label")):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return str(path)


def test_gap_splits_episodes(tmp_path):
    rows = [
        (t, "172.16.0.1", "192.168.10.50", p, "port_scan")
        for t, p in ((100, 1), (101, 2), (102, 3), (500, 4), (501, 5))
    ]
    m = make_manifest.make_manifest(_csv(tmp_path / "f.csv", rows))
    first, second = m["episodes"]
    assert (first["episode_id"], first["start"], first["end"]) == ("port_scan-001", 100.0, 102.0)
    assert (second["episode_id"], second["start"], second["end"]) == ("port_scan-002", 500.0, 501.0)
    assert first["params"]["flows"] == 3
    assert first["params"]["distinct_dst_ports"] == 3
    assert first["attackers"] == ["172.16.0.1"]
    assert first["targets"] == ["192.168.10.50"]


def test_one_episode_per_class_and_attacker(tmp_path):
    rows = [
        (100, "10.0.0.1", "10.0.1.1", 22, "port_scan"),
        (100, "10.0.0.2", "10.0.1.1", 22, "port_scan"),
        (101, "10.0.0.1", "10.0.1.1", 80, "dos"),
    ]
    m = make_manifest.make_manifest(_csv(tmp_path / "f.csv", rows))
    assert [(e["class"], e["attackers"][0]) for e in m["episodes"]] == [
        ("port_scan", "10.0.0.1"),
        ("port_scan", "10.0.0.2"),
        ("dos", "10.0.0.1"),
    ]


def test_normal_traffic_makes_no_episode(tmp_path):
    rows = [(100, "10.0.0.1", "10.0.1.1", 80, "normal"), (101, "10.0.0.1", "10.0.1.1", 80, "")]
    m = make_manifest.make_manifest(_csv(tmp_path / "f.csv", rows))
    assert m["episodes"] == []
    assert m["source"] == "flowfile"
    assert m["seed"] is None


def test_many_targets_are_collapsed_to_networks():
    ips = {"10.0.0.1", "10.0.0.2", "10.0.0.3"}
    assert make_manifest.collapse_hosts(ips, 5) == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
    assert make_manifest.collapse_hosts(ips, 2) == ["10.0.0.0/24"]


def test_unknown_attack_label_is_an_error(tmp_path):
    rows = [(100, "10.0.0.1", "10.0.1.1", 80, "ransomware")]
    with pytest.raises(ValueError, match="unknown attack label"):
        make_manifest.make_manifest(_csv(tmp_path / "f.csv", rows))


def test_missing_columns_are_an_error(tmp_path):
    path = _csv(tmp_path / "f.csv", [(1, 2)], header=("a", "b"))
    with pytest.raises(ValueError, match="missing columns"):
        make_manifest.make_manifest(path)


def test_cli_writes_manifest_next_to_the_data_file(tmp_path, capsys):
    src = _csv(tmp_path / "f.csv", [(100, "10.0.0.1", "10.0.1.1", 22, "brute_force")])
    assert make_manifest.main([src, "--notes", "unit test"]) == 0
    written = json.loads((tmp_path / "f.csv.manifest.json").read_text())
    assert written["dataset"] == "LABELLED/f"
    assert written["notes"] == "unit test"
    assert written["episodes"][0]["class"] == "brute_force"
    assert "brute_force-001" in capsys.readouterr().out
