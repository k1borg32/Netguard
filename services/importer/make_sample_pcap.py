"""Write a tiny deterministic .pcap test fixture to data/pcap/sample.pcap.

NOT a traffic simulator — it writes one static capture file, used to exercise
the PCAP import path. Requires dpkt (already in the importer image).
"""

from __future__ import annotations

import socket

import dpkt

OUT = "data/pcap/sample.pcap"


def tcp_packet(src: str, dst: str, sport: int, dport: int, flags: int) -> bytes:
    tcp = dpkt.tcp.TCP(sport=sport, dport=dport, flags=flags, seq=0, ack=0, win=8192)
    ip = dpkt.ip.IP(src=socket.inet_aton(src), dst=socket.inet_aton(dst), p=dpkt.ip.IP_PROTO_TCP)
    ip.data = tcp
    ip.len = len(ip)
    eth = dpkt.ethernet.Ethernet(
        src=b"\x00\x00\x00\x00\x00\x01",
        dst=b"\x00\x00\x00\x00\x00\x02",
        type=dpkt.ethernet.ETH_TYPE_IP,
    )
    eth.data = ip
    return bytes(eth)


def main() -> None:
    t = 1700000000.0
    pkts = []
    # port scan: one source SYNs 120 distinct ports on one target (> threshold 100)
    for i in range(120):
        pkts.append((t + i * 0.001, tcp_packet("10.0.0.66", "10.0.0.10", 40000 + i, 1 + i, dpkt.tcp.TH_SYN)))
    # a few normal 2-packet flows
    for i in range(5):
        base = t + 2 + i
        pkts.append((base, tcp_packet("10.0.0.5", "10.0.0.9", 51000 + i, 443, dpkt.tcp.TH_SYN)))
        pkts.append((base + 0.1, tcp_packet("10.0.0.5", "10.0.0.9", 51000 + i, 443, dpkt.tcp.TH_SYN | dpkt.tcp.TH_ACK)))

    with open(OUT, "wb") as f:
        w = dpkt.pcap.Writer(f)
        for ts, buf in pkts:
            w.writepkt(buf, ts=ts)
    print(f"wrote {len(pkts)} packets -> {OUT}")


if __name__ == "__main__":
    main()
