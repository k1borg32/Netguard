"""Robustness tests for the importer (SEC-02): bad input must give a clear error
(and a summary), never a crash or silent data loss. No dpkt or Docker needed."""

import importlib
import pathlib
import struct
import sys

import pytest

BASE = pathlib.Path(__file__).resolve().parents[2] / "services" / "importer"
sys.path.insert(0, str(BASE))
importer = importlib.import_module("importer")
pcap_reader = importlib.import_module("pcap_reader")


def _pcap_bytes(n_records: int, linktype: int = 1, cut: int = 0) -> bytes:
    data = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, linktype)
    payload = b"\x00" * 54
    for i in range(n_records):
        data += struct.pack("<IIII", 1700000000 + i, 0, len(payload), len(payload)) + payload
    return data[:-cut] if cut else data


def test_check_pcap_valid(tmp_path):
    p = tmp_path / "ok.pcap"
    p.write_bytes(_pcap_bytes(3))
    assert pcap_reader.check_pcap(str(p)) == (3, False)


@pytest.mark.parametrize("cut", [10, 60])
def test_check_pcap_detects_truncation(tmp_path, cut):
    """SEC-02: a cut-off capture is flagged, not silently imported."""
    p = tmp_path / "cut.pcap"
    p.write_bytes(_pcap_bytes(3, cut=cut))
    assert pcap_reader.check_pcap(str(p)) == (2, True)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"\x0a\x0d\x0d\x0a" + b"\x00" * 40, "pcapng"),
        (b"hello world, this is not a capture at all", "not a pcap"),
        (b"abc", "too short"),
        (_pcap_bytes(1, linktype=113), "link type"),
    ],
)
def test_check_pcap_rejects_wrong_files(tmp_path, content, message):
    p = tmp_path / "x.pcap"
    p.write_bytes(content)
    with pytest.raises(pcap_reader.PcapFormatError, match=message):
        pcap_reader.check_pcap(str(p))


def test_unsupported_extension(tmp_path):
    p = tmp_path / "flows.txt"
    p.write_text("x")
    with pytest.raises(importer.InputError, match="unsupported"):
        list(importer._raw_records(str(p), []))


def test_pcapng_extension_has_clear_error(tmp_path):
    p = tmp_path / "capture.pcapng"
    p.write_bytes(b"\x0a\x0d\x0d\x0a")
    with pytest.raises(importer.InputError, match="pcapng"):
        list(importer._raw_records(str(p), []))


def test_garbage_pcap_is_input_error(tmp_path):
    p = tmp_path / "bad.pcap"
    p.write_bytes(b"not a capture at all, just text" * 3)
    with pytest.raises(importer.InputError, match="not a pcap"):
        list(importer._raw_records(str(p), []))


def test_binary_file_named_csv_is_input_error(tmp_path):
    p = tmp_path / "bin.csv"
    p.write_bytes(b"\xff\xfe\x00\x81" * 64)
    with pytest.raises(importer.InputError, match="CSV"):
        list(importer._raw_records(str(p), []))


def test_csv_missing_header_columns(tmp_path):
    p = tmp_path / "wrong.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(importer.InputError, match="missing columns"):
        list(importer._raw_records(str(p), []))


def test_valid_csv_streams_rows(tmp_path):
    p = tmp_path / "ok.csv"
    p.write_text(
        "ts_start,duration_ms,src_ip,dst_ip,src_port,dst_port,protocol,packets,bytes\n"
        "1,2,10.0.0.1,10.0.0.2,1,2,6,1,60\n"
    )
    records = list(importer._raw_records(str(p), []))
    assert len(records) == 1
    assert records[0][0] == "row"


def test_suspicious_pattern_label_is_accepted():
    """Allowed labels come from the schema, so new enum values are never rejected."""
    assert importer._label("suspicious_pattern") == "suspicious_pattern"
