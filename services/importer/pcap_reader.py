"""PCAP -> flows (owner: Member 1).

check_pcap() validates the file header and walks the record headers WITHOUT
reading packet data, so a wrong file type or a truncated capture is detected up
front. iter_packets() reads a classic Ethernet .pcap with dpkt and yields one
Packet per IP datagram. extract_flows() groups packets into unidirectional
5-tuple flows and returns flow.v1 field dicts (no envelope; the importer adds
flow_id/trace_id/ingested_at and validates).

check_pcap and extract_flows are pure Python, so they are unit-testable without
dpkt; only iter_packets needs dpkt, and it imports it lazily.

Limit: extract_flows keeps every flow of the capture in memory. Use the PCAP
path for small captures only; big datasets (e.g. CIC-IDS2017) go in as flow CSV.
"""

from __future__ import annotations

import os
import struct

PROTO_NAME = {6: "TCP", 17: "UDP", 1: "ICMP", 58: "ICMP"}
# TCP flag bit -> schema letter (flow.v1 pattern ^[FSRPAUEC]*$), fixed order.
TCP_FLAG_BITS = [
    (0x01, "F"),
    (0x02, "S"),
    (0x04, "R"),
    (0x08, "P"),
    (0x10, "A"),
    (0x20, "U"),
    (0x40, "E"),
    (0x80, "C"),
]

PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"
# First 4 bytes of a classic pcap -> byte order of the rest (micro/nanosecond variants).
_MAGIC_ENDIAN = {
    b"\xd4\xc3\xb2\xa1": "<",
    b"\xa1\xb2\xc3\xd4": ">",
    b"\x4d\x3c\xb2\xa1": "<",
    b"\xa1\xb2\x3c\x4d": ">",
}
_GLOBAL_HEADER_LEN = 24
_RECORD_HEADER_LEN = 16
LINKTYPE_ETHERNET = 1


class PcapFormatError(ValueError):
    """The file is not a classic Ethernet pcap that this reader can handle."""


class Packet:
    """One IP packet's fields (plain class: survives path-based test imports)."""

    __slots__ = ("ts", "src_ip", "dst_ip", "src_port", "dst_port", "protocol", "length", "flags")

    def __init__(self, ts, src_ip, dst_ip, src_port, dst_port, protocol, length, flags=0):
        self.ts = ts
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_port = src_port
        self.dst_port = dst_port
        self.protocol = protocol
        self.length = length
        self.flags = flags


def flags_to_str(bits: int) -> str:
    return "".join(letter for bit, letter in TCP_FLAG_BITS if bits & bit)


def check_pcap(path: str) -> tuple[int, bool]:
    """Validate a classic pcap and return (complete_records, truncated).

    Raises PcapFormatError for files that are not a classic Ethernet pcap
    (wrong magic, pcapng, non-Ethernet link type, too short). Does not read
    packet payloads: it only follows the record headers.
    """
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(_GLOBAL_HEADER_LEN)
        if len(head) < _GLOBAL_HEADER_LEN:
            raise PcapFormatError("file is too short to be a pcap capture")
        magic = head[:4]
        if magic == PCAPNG_MAGIC:
            raise PcapFormatError(
                "pcapng is not supported, only classic .pcap (convert with: editcap -F pcap in.pcapng out.pcap)"
            )
        endian = _MAGIC_ENDIAN.get(magic)
        if endian is None:
            raise PcapFormatError("not a pcap file (bad magic number)")
        linktype = struct.unpack(endian + "I", head[20:24])[0]
        if linktype != LINKTYPE_ETHERNET:
            raise PcapFormatError(f"unsupported link type {linktype} (only Ethernet is supported)")

        records = 0
        truncated = False
        pos = _GLOBAL_HEADER_LEN
        while pos < size:
            if size - pos < _RECORD_HEADER_LEN:
                truncated = True
                break
            f.seek(pos)
            incl_len = struct.unpack(endian + "IIII", f.read(_RECORD_HEADER_LEN))[2]
            if pos + _RECORD_HEADER_LEN + incl_len > size:
                truncated = True
                break
            pos += _RECORD_HEADER_LEN + incl_len
            records += 1
    return records, truncated


def extract_flows(packets) -> list[dict]:
    """Group packets into unidirectional 5-tuple flows -> flow.v1 field dicts.

    First-seen insertion order is preserved, so re-running on the same capture
    yields the same order -> the importer's deterministic flow_id stays stable.
    """
    flows: dict[tuple, dict] = {}
    flag_bits: dict[tuple, int] = {}
    last_ts: dict[tuple, float] = {}

    for p in packets:
        key = (p.src_ip, p.dst_ip, p.src_port, p.dst_port, p.protocol)
        f = flows.get(key)
        if f is None:
            flows[key] = {
                "ts_start": p.ts,
                "duration_ms": 0.0,
                "src_ip": p.src_ip,
                "dst_ip": p.dst_ip,
                "src_port": p.src_port,
                "dst_port": p.dst_port,
                "protocol": p.protocol,
                "packets": 1,
                "bytes": p.length,
                "tcp_flags": None,
                "label": None,
            }
            flag_bits[key] = p.flags
            last_ts[key] = p.ts
        else:
            f["packets"] += 1
            f["bytes"] += p.length
            flag_bits[key] |= p.flags
            f["ts_start"] = min(f["ts_start"], p.ts)
            last_ts[key] = max(last_ts[key], p.ts)

    out = []
    for key, f in flows.items():
        f["duration_ms"] = round((last_ts[key] - f["ts_start"]) * 1000.0, 3)
        if f["protocol"] == "TCP":
            f["tcp_flags"] = flags_to_str(flag_bits[key])
        out.append(f)
    return out


def iter_packets(path: str, max_records: int | None = None):
    """Yield Packet objects from a classic .pcap file. Requires dpkt.

    max_records limits how many records are read (use the complete-record count
    from check_pcap so a cut-off tail record is never parsed).
    """
    import socket

    import dpkt

    with open(path, "rb") as fh:
        for n, (ts, buf) in enumerate(dpkt.pcap.Reader(fh)):
            if max_records is not None and n >= max_records:
                break
            pkt = _parse(ts, buf, socket, dpkt)
            if pkt is not None:
                yield pkt


def _parse(ts, buf, socket, dpkt):
    try:
        eth = dpkt.ethernet.Ethernet(buf)
        ip = eth.data
    except Exception:
        return None
    if isinstance(ip, dpkt.ip.IP):
        family, proto_num = socket.AF_INET, ip.p
    elif isinstance(ip, dpkt.ip6.IP6):
        family, proto_num = socket.AF_INET6, ip.nxt
    else:
        return None  # ARP and other non-IP frames

    protocol = PROTO_NAME.get(proto_num, "OTHER")
    src = socket.inet_ntop(family, ip.src)
    dst = socket.inet_ntop(family, ip.dst)

    sport = dport = flags = 0
    l4 = ip.data
    if protocol in ("TCP", "UDP") and hasattr(l4, "sport"):
        sport, dport = int(l4.sport), int(l4.dport)
        if protocol == "TCP":
            flags = int(getattr(l4, "flags", 0))

    return Packet(float(ts), src, dst, sport, dport, protocol, len(buf), flags)
