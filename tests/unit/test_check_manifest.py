"""Unit tests for the ground-truth check (services/importer/check_manifest.py)."""

import csv
import importlib
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parents[2] / "services" / "importer"
sys.path.insert(0, str(BASE))
make_manifest = importlib.import_module("make_manifest")
check_manifest = importlib.import_module("check_manifest")

ROWS = [
    (100, "10.0.0.1", "10.0.1.1", 1, "port_scan"),
    (101, "10.0.0.1", "10.0.1.1", 2, "port_scan"),
    (102, "10.0.0.9", "10.0.1.1", 80, "normal"),
    (500, "10.0.0.1", "10.0.1.1", 3, "port_scan"),
]


def _setup(tmp_path):
    src = tmp_path / "f.csv"
    with open(src, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("ts_start", "src_ip", "dst_ip", "dst_port", "label"))
        w.writerows(ROWS)
    manifest = make_manifest.make_manifest(str(src))
    path = tmp_path / "f.csv.manifest.json"
    path.write_text(json.dumps(manifest))
    return str(src), path, manifest


def test_consistent_manifest_passes(tmp_path):
    src, _, _ = _setup(tmp_path)
    r = check_manifest.check(src)
    assert r["problems"] == []
    assert (r["attack_total"], r["covered"]) == (3, 3)


def test_removed_episode_leaves_flows_uncovered(tmp_path):
    src, path, manifest = _setup(tmp_path)
    manifest["episodes"] = manifest["episodes"][:1]
    path.write_text(json.dumps(manifest))
    r = check_manifest.check(src)
    assert r["uncovered"]["port_scan"] == 1
    assert any("outside every episode" in p for p in r["problems"])


def test_flow_count_mismatch_is_reported(tmp_path):
    src, path, manifest = _setup(tmp_path)
    manifest["episodes"][0]["params"]["flows"] += 1
    path.write_text(json.dumps(manifest))
    r = check_manifest.check(src)
    assert any("manifest says" in p for p in r["problems"])


def test_invalid_manifest_is_a_problem_not_a_crash(tmp_path):
    src, path, manifest = _setup(tmp_path)
    del manifest["episodes"]
    path.write_text(json.dumps(manifest))
    r = check_manifest.check(src)
    assert "manifest.v1.json" in r["problems"][0]


def test_cli_exit_codes(tmp_path, capsys):
    src, path, manifest = _setup(tmp_path)
    assert check_manifest.main([src]) == 0
    manifest["episodes"] = manifest["episodes"][:1]
    path.write_text(json.dumps(manifest))
    assert check_manifest.main([src]) == 1
    assert "FAILED" in capsys.readouterr().out
