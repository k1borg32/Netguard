"""Unit tests for the CIC-IDS2017 converter (services/importer/convert_cic.py).

Test plan: UT-20.
"""

import csv
import importlib
import pathlib
import sys
import time
from datetime import UTC, datetime

import pytest

from netguard_common.messages import validate_flow

BASE = pathlib.Path(__file__).resolve().parents[2] / "services" / "importer"
sys.path.insert(0, str(BASE))
convert_cic = importlib.import_module("convert_cic")
importer = importlib.import_module("importer")

HEADER = [
    "Flow ID",
    " Source IP",
    " Source Port",
    " Destination IP",
    " Destination Port",
    " Protocol",
    " Timestamp",
    " Flow Duration",
    " Total Fwd Packets",
    " Total Backward Packets",
    "Total Length of Fwd Packets",
    " Total Length of Bwd Packets",
    "FIN Flag Count",
    " SYN Flag Count",
    " RST Flag Count",
    " PSH Flag Count",
    " ACK Flag Count",
    " URG Flag Count",
    " CWE Flag Count",
    " ECE Flag Count",
    " Label",
]


def _row(**kw):
    base = {
        "Flow ID": "x",
        " Source IP": "172.16.0.1",
        " Source Port": "5000",
        " Destination IP": "192.168.10.50",
        " Destination Port": "80",
        " Protocol": "6",
        " Timestamp": "7/7/2017 3:30",
        " Flow Duration": "2000000",
        " Total Fwd Packets": "3",
        " Total Backward Packets": "2",
        "Total Length of Fwd Packets": "100",
        " Total Length of Bwd Packets": "50",
        "FIN Flag Count": "0",
        " SYN Flag Count": "1",
        " RST Flag Count": "0",
        " PSH Flag Count": "0",
        " ACK Flag Count": "1",
        " URG Flag Count": "0",
        " CWE Flag Count": "0",
        " ECE Flag Count": "0",
        " Label": "BENIGN",
    }
    base.update(kw)
    return [base[h] for h in HEADER]


def _write(path, rows):
    with open(path, "w", newline="", encoding="latin-1") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    return path


def _read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _utc(*args):
    return datetime(*args, tzinfo=UTC).timestamp()


def test_convert_maps_fields_and_output_is_valid(tmp_path):
    src = _write(
        tmp_path / "in.csv",
        [
            _row(),
            _row(**{" Label": "PortScan", " Source Port": "5001", " Destination Port": "22", " ACK Flag Count": "0"}),
        ],
    )
    dst = tmp_path / "out.csv"
    stats = convert_cic.convert(str(src), str(dst))
    rows = _read(dst)
    assert stats["written"] == 2
    assert [r["label"] for r in rows] == ["normal", "port_scan"]
    first = rows[0]
    assert float(first["ts_start"]) == _utc(2017, 7, 7, 15, 30)  # 3:30 without AM/PM = afternoon
    assert float(first["duration_ms"]) == 2000.0
    assert (first["packets"], first["bytes"], first["tcp_flags"], first["protocol"]) == ("5", "150", "SA", "TCP")
    assert rows[1]["tcp_flags"] == "S"
    for i, row in enumerate(rows):
        flow = importer.finalise_flow(importer.normalise_row(row), "cic.csv", i, time.time(), "traceabc123", "flowfile")
        validate_flow(flow)


def test_unmapped_classes_are_skipped_unless_requested(tmp_path):
    src = _write(tmp_path / "in.csv", [_row(**{" Label": "Web Attack \x96 Brute Force"})])
    stats = convert_cic.convert(str(src), str(tmp_path / "a.csv"))
    assert stats["written"] == 0
    assert stats["skipped"]["unmapped label 'web attack brute force'"] == 1
    stats = convert_cic.convert(str(src), str(tmp_path / "b.csv"), include_other=True)
    assert stats["labels"] == {"brute_force": 1}


def test_negative_duration_is_skipped(tmp_path):
    src = _write(tmp_path / "in.csv", [_row(**{" Flow Duration": "-1"})])
    stats = convert_cic.convert(str(src), str(tmp_path / "out.csv"))
    assert stats["written"] == 0
    assert stats["skipped"]["bad duration"] == 1


def test_parse_timestamp_variants():
    assert convert_cic.parse_timestamp("7/7/2017 3:30") == (_utc(2017, 7, 7, 15, 30), False)
    assert convert_cic.parse_timestamp("7/7/2017 8:59")[0] == _utc(2017, 7, 7, 8, 59)
    assert convert_cic.parse_timestamp("7/7/2017 15:30:10") == (_utc(2017, 7, 7, 15, 30, 10), True)
    assert convert_cic.parse_timestamp("7/7/2017 3:30", pm_before=0)[0] == _utc(2017, 7, 7, 3, 30)
    assert convert_cic.parse_timestamp("2017-07-07 15:30:10") == (_utc(2017, 7, 7, 15, 30, 10), True)
    with pytest.raises(ValueError):
        convert_cic.parse_timestamp("yesterday")


def test_norm_label_removes_the_broken_dash():
    assert convert_cic.norm_label("Web Attack \x96 Brute Force") == "web attack brute force"
    assert convert_cic.norm_label("DoS Hulk") == "dos hulk"


def test_wrong_file_gives_clear_error(tmp_path):
    p = tmp_path / "wrong.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="missing columns"):
        convert_cic.convert(str(p), str(tmp_path / "out.csv"))


def test_spread_minutes(tmp_path):
    src = _write(tmp_path / "in.csv", [_row(), _row(**{" Source Port": "5001"})])
    stats = convert_cic.convert(str(src), str(tmp_path / "out.csv"), spread_minutes=True)
    ts = [float(r["ts_start"]) for r in _read(tmp_path / "out.csv")]
    assert stats["minute_resolution"] == 2
    assert ts[1] - ts[0] == 30.0


def test_time_window(tmp_path):
    src = _write(tmp_path / "in.csv", [_row(), _row(**{" Timestamp": "7/7/2017 4:10"})])
    convert_cic.convert(str(src), str(tmp_path / "out.csv"), from_time="16:00")
    assert len(_read(tmp_path / "out.csv")) == 1
