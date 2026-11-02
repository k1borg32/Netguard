"""Rule-based detection (F06, spec 9.1): deterministic checks of window features against configured thresholds.

Every rule returns Findings: what was observed, the threshold it crossed, the key feature values and a sentence
that explains it (F09). Severity and confidence are added by the engine from observed / threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import DetectionConfig
from .windows import SourceWindow, TargetWindow


@dataclass
class Finding:
    type: str
    method: str
    src_ip: str | None
    dst_ip: str | None
    observed: float
    threshold: float
    explanation: str
    features: dict[str, float | int | str | bool] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        return self.observed / self.threshold


def port_scan(cfg: DetectionConfig, src: str, w: SourceWindow) -> list[Finding]:
    """One source -> many different destination ports within a short window."""
    thr = cfg.port_scan.unique_dst_ports_threshold
    n = len(w.dst_ports)
    if n < thr:
        return []
    dst = next(iter(w.dst_ips)) if len(w.dst_ips) == 1 else None
    return [
        Finding(
            type="port_scan",
            method="rule",
            src_ip=src,
            dst_ip=dst,
            observed=n,
            threshold=thr,
            explanation=(
                f"{src} contacted {n} distinct destination ports on {len(w.dst_ips)} host(s) "
                f"in {cfg.port_scan.window_s} s (threshold {thr})."
            ),
            features={"unique_dst_ports": n, "unique_dst_ips": len(w.dst_ips), "flows": w.flows},
        )
    ]


def _dos_trigger(cfg: DetectionConfig, conns: int, packets: int) -> tuple[int, int, str] | None:
    """(observed, threshold, what) for whichever of connections / packets is further above its threshold."""
    c = cfg.dos
    by_conns = (conns, c.connections_to_target_threshold, "connections")
    by_packets = (packets, c.packets_to_target_threshold, "packets")
    best = max(by_conns, by_packets, key=lambda t: t[0] / t[1])
    return best if best[0] >= best[1] else None


def dos_from_source(cfg: DetectionConfig, src: str, w: SourceWindow) -> list[Finding]:
    """One source -> unusually many connections or packets at one target."""
    c = cfg.dos
    out = []
    for dst, conns in w.conns_per_dst.items():
        packets = w.packets_per_dst[dst]
        trigger = _dos_trigger(cfg, conns, packets)
        if trigger is None:
            continue
        observed, thr, what = trigger
        out.append(
            Finding(
                type="dos",
                method="rule",
                src_ip=src,
                dst_ip=dst,
                observed=observed,
                threshold=thr,
                explanation=f"{src} sent {observed} {what} to {dst} in {c.window_s} s (threshold {thr}).",
                features={"connections": conns, "packets": packets, "triggered_by": what},
            )
        )
    return out


def dos_on_target(cfg: DetectionConfig, dst: str, w: TargetWindow) -> list[Finding]:
    """Many sources together -> one target (DDoS-like). Source is null because there is no single one."""
    c = cfg.dos
    sources = len(w.conns_per_src)
    if sources < c.ddos_min_sources:
        return []
    trigger = _dos_trigger(cfg, w.flows, w.packets)
    if trigger is None:
        return []
    observed, thr, what = trigger
    top_src, top_conns = w.conns_per_src.most_common(1)[0]
    return [
        Finding(
            type="dos",
            method="rule",
            src_ip=None,
            dst_ip=dst,
            observed=observed,
            threshold=thr,
            explanation=(
                f"{dst} received {observed} {what} from {sources} sources in {c.window_s} s "
                f"(threshold {thr}); top source {top_src} with {top_conns} connections."
            ),
            features={
                "connections": w.flows,
                "packets": w.packets,
                "unique_src_ips": sources,
                "top_src_ip": top_src,
                "top_src_connections": top_conns,
                "triggered_by": what,
            },
        )
    ]


def brute_force(cfg: DetectionConfig, src: str, w: SourceWindow) -> list[Finding]:
    """One source -> many repeated connection attempts to the same login service of one host."""
    thr = cfg.brute_force.attempts_same_service_threshold
    return [
        Finding(
            type="brute_force",
            method="rule",
            src_ip=src,
            dst_ip=dst,
            observed=n,
            threshold=thr,
            explanation=(
                f"{src} made {n} connection attempts to {dst}:{port} in {cfg.brute_force.window_s} s (threshold {thr})."
            ),
            features={"attempts": n, "dst_port": port},
        )
        for (dst, port), n in w.attempts_per_service.items()
        if n >= thr
    ]


def suspicious_pattern(cfg: DetectionConfig, src: str, w: SourceWindow, known_dsts: set[str]) -> list[Finding]:
    """Abnormal connection pattern: the source talks to many hosts that are not in its recent connection profile."""
    c = cfg.suspicious_pattern
    new = len(w.dst_ips - known_dsts)
    if new < c.new_dst_ips_threshold:
        return []
    return [
        Finding(
            type="suspicious_pattern",
            method="rule",
            src_ip=src,
            dst_ip=None,
            observed=new,
            threshold=c.new_dst_ips_threshold,
            explanation=(
                f"{src} contacted {new} hosts it had not contacted in the previous {c.profile_window_s} s "
                f"({len(w.dst_ips)} hosts in total, profile of {len(known_dsts)} known hosts) "
                f"in {c.window_s} s (threshold {c.new_dst_ips_threshold})."
            ),
            features={"new_dst_ips": new, "unique_dst_ips": len(w.dst_ips), "known_dst_ips": len(known_dsts)},
        )
    ]
