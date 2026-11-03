"""Broker topic names. Change them here only.

Partitioning rule: every message on FLOWS_RAW is keyed by src_ip.
All flows from one source land on one partition -> one processor instance,
so per-source time windows stay correct when the processor is scaled (NFR03).
"""

FLOWS_RAW = "flows.raw"  # importer (load generator in tests) -> processor   (key: src_ip)
DETECTIONS = "detections"  # processor -> alert/persister        (key: detection_id)
DEAD_LETTER = "flows.deadletter"  # anything that failed validation      (key: none)

PARTITIONS = {
    FLOWS_RAW: 6,
    DETECTIONS: 3,
    DEAD_LETTER: 1,
}
