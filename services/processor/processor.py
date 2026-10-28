"""Stream processor + detection engine (owner: Member 2).

Scalable: run N instances (`docker compose up --scale processor=3`). They share
consumer group "processor"; Kafka assigns partitions, and because flows are
keyed by src_ip, each source's windows live in exactly one instance.

The detection logic is in `detection_engine/` (broker-free, unit-tested); this
file only connects it to the broker. Design: Docs/ArchitectureDocument/detection/README.md
"""

from __future__ import annotations

import os
import sys
import time

from detection_engine import ConfigError, DetectionEngine, load_config

from netguard_common import get_logger, setup_logging, trace_context

log = get_logger("processor")

STATS_EVERY_S = 30.0


def main() -> None:
    from netguard_common import topics
    from netguard_common.broker import encode, ensure_topics, make_consumer, make_producer, poll_batch

    setup_logging("processor")
    path = os.getenv("DETECTION_CONFIG", "/app/config/detection.yaml")
    try:
        cfg = load_config(path)
    except ConfigError as e:
        log.error("invalid detection config, not starting", extra={"path": path, "error": str(e)})
        sys.exit(2)
    engine = DetectionEngine(cfg)

    ensure_topics()
    consumer = make_consumer("processor", [topics.FLOWS_RAW])
    producer = make_producer()
    log.info("processor started", extra={"instance": os.getenv("HOSTNAME"), "config": path})

    last_stats = time.time()
    try:
        while True:
            got = 0
            now = time.time()
            for _, flow in poll_batch(consumer):
                if not engine.add(flow, now):
                    log.warning("flow skipped: missing or invalid field", extra={"flow_id": flow.get("flow_id")})
                got += 1
            now = time.time()
            for det in engine.evaluate(now):
                with trace_context(det["trace_ids"][0]):
                    producer.produce(topics.DETECTIONS, key=det["detection_id"], value=encode(det))
                    log.info(
                        "detection",
                        extra={
                            "detection_id": det["detection_id"],
                            "type": det["type"],
                            "method": det["method"],
                            "severity": det["severity"],
                            "alert": det["alert"],
                            "latency_s": round(now - det["last_ingested_at"], 3),
                        },
                    )
            producer.poll(0)
            if got:
                # KNOWN LIMITATION (doc it in test report): offsets are committed before open windows
                # close, so a crash loses at most one window of in-memory state. Fix = replay from
                # (window_start) offsets or a state store. Discuss with Member 2 in week 2.
                consumer.commit(asynchronous=True)
            if now - last_stats >= STATS_EVERY_S:
                last_stats = now
                log.info("engine stats", extra=engine.stats())
    finally:
        producer.flush(5)
        consumer.close()


if __name__ == "__main__":
    main()
