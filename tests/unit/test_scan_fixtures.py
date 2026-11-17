"""Unit tests for the small port-scan test files and the slice tool (services/importer/make_scan_fixtures.py,
slice_flows.py): the input of the end-to-end tests ST-02, ST-03 and IT-09.

Test plan: UT-25.
"""

import csv
import importlib
import json
import pathlib
import sys

import pytest

BASE = pathlib.Path(__file__).resolve().parents[2] / "services" / "importer"
sys.path.insert(0, str(BASE))
fixtures = importlib.import_module("make_scan_fixtures")
slice_flows = importlib.import_module("slice_flows")
check_manifest = importlib.import_module("check_manifest")
importer = importlib.import_module("importer")


def _write_all(folder, attacker=fixtures.ATTACKER):
    pcap = folder / "scan.pcap"
    flow_file = folder / "scan.csv"
    fixtures.write_pcap(pcap, attacker)
    fixtures.write_csv(flow_file, attacker)
    fixtures.write_manifest(flow_file)
    return pcap, flow_file


def test_files_are_the_same_on_every_run(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _write_all(tmp_path / "a")
    _write_all(tmp_path / "b")

    for name in ("scan.pcap", "scan.csv", "scan.csv.manifest.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_csv_rows_are_valid_flows_and_the_scan_is_above_the_rule(tmp_path):
    _, flow_file = _write_all(tmp_path)

    with open(flow_file, newline="") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows):
        importer.validate_flow(importer.build_flow(row, "scan.csv", i, 1.0, "0" * 32))
    scan = [r for r in rows if r["label"] == "port_scan"]

    assert len(scan) == 300
    assert len({r["dst_port"] for r in scan}) == 300  # the default rule fires at 100 ports in 10 s
    assert {r["src_ip"] for r in scan} == {fixtures.ATTACKER}


def test_manifest_has_one_episode_and_matches_the_csv(tmp_path):
    _, flow_file = _write_all(tmp_path, attacker="10.99.1.2")

    manifest = json.loads(pathlib.Path(f"{flow_file}.manifest.json").read_text())
    result = check_manifest.check(str(flow_file))

    assert [(e["class"], e["attackers"]) for e in manifest["episodes"]] == [("port_scan", ["10.99.1.2"])]
    assert result["problems"] == []
    assert result["per_episode"]["port_scan-001"] == (300, 300)


def test_pcap_gives_the_same_scan_as_flows(tmp_path):
    pytest.importorskip("dpkt")
    pcap_reader = importlib.import_module("pcap_reader")
    pcap, _ = _write_all(tmp_path)

    records, truncated = pcap_reader.check_pcap(str(pcap))
    found = pcap_reader.extract_flows(pcap_reader.iter_packets(str(pcap)))
    scan = [f for f in found if f["src_ip"] == fixtures.ATTACKER]

    assert truncated is False and records > len(found)  # the normal flows have 2 packets
    assert len(found) == 316 and len(scan) == 300
    assert len({f["dst_port"] for f in scan}) == 300


def test_slice_keeps_the_range_and_writes_a_matching_manifest(tmp_path):
    _, flow_file = _write_all(tmp_path)
    out = tmp_path / "slice.csv"

    code = slice_flows.main(
        [str(flow_file), str(out), "--episode", "port_scan-001", "--pad", "0", "--max-seconds", "4"]
    )

    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert code == 0
    assert all(fixtures.START <= float(r["ts_start"]) <= fixtures.START + 4 for r in rows)
    assert 0 < sum(r["label"] == "port_scan" for r in rows) < 300
    assert check_manifest.check(str(out))["problems"] == []


def test_slice_with_an_unknown_episode_or_an_empty_range_fails(tmp_path, capsys):
    _, flow_file = _write_all(tmp_path)
    out = tmp_path / "slice.csv"

    assert slice_flows.main([str(flow_file), str(out), "--episode", "dos-009"]) == 1
    assert "no episode 'dos-009'" in capsys.readouterr().err
    assert slice_flows.main([str(flow_file), str(out), "--from", "1", "--to", "2"]) == 1
    assert "no flows between" in capsys.readouterr().err
    assert slice_flows.main([str(flow_file), str(out)]) == 1
