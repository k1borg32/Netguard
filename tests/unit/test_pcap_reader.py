"""Unit tests for PCAP flow extraction (services/importer/pcap_reader.py).

Covers flow grouping, flag accumulation and schema validity for the PCAP path
(IT-03) without needing dpkt or a capture file.
"""

import importlib.util
import pathlib
import time

from netguard_common.messages import validate_flow

BASE = pathlib.Path(__file__).resolve().parents[2] / "services" / "importer"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pcap_reader = _load("pcap_reader", BASE / "pcap_reader.py")
importer = _load("importer", BASE / "importer.py")
Packet = pcap_reader.Packet


def _packets():
    pkts = []
    # one source hits 15 distinct destination ports (a scan)
    for i, port in enumerate(range(20, 35)):
        pkts.append(Packet(1700000000.0 + i * 0.01, "10.0.0.66", "10.0.0.10", 40000 + i, port, "TCP", 60, 0x02))
    # one normal flow, two packets (SYN then ACK)
    pkts.append(Packet(1700000001.0, "10.0.0.5", "10.0.0.9", 51514, 443, "TCP", 100, 0x02))
    pkts.append(Packet(1700000001.2, "10.0.0.5", "10.0.0.9", 51514, 443, "TCP", 140, 0x10))
    return pkts


def test_flags_to_str():
    assert pcap_reader.flags_to_str(0x02) == "S"
    assert pcap_reader.flags_to_str(0x12) == "SA"
    assert pcap_reader.flags_to_str(0x11) == "FA"


def test_extract_flows_groups_by_5tuple():
    flows = pcap_reader.extract_flows(_packets())
    assert len(flows) == 16  # 15 scan flows + 1 normal
    scan = [f for f in flows if f["src_ip"] == "10.0.0.66"]
    assert len({f["dst_port"] for f in scan}) == 15


def test_extracted_flow_aggregates_and_validates():
    flows = pcap_reader.extract_flows(_packets())
    normal = next(f for f in flows if f["src_ip"] == "10.0.0.5")
    assert normal["packets"] == 2
    assert normal["bytes"] == 240
    assert normal["tcp_flags"] == "SA"
    assert normal["duration_ms"] == 200.0
    flow = importer.finalise_flow(normal, "sample.pcap", 0, time.time(), "traceabc123", "pcap")
    validate_flow(flow)
    assert flow["source"] == "pcap"
