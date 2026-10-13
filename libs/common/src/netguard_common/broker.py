"""Thin wrappers around confluent-kafka (works with Kafka and Redpanda).

Delivery semantics: at-least-once. Consumers commit offsets only AFTER the
work is done (produced downstream / written to DB). A crash means messages
are re-delivered, so every consumer must be idempotent (deterministic IDs + upserts).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

from confluent_kafka import Consumer, KafkaError, Message, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from netguard_common import topics
from netguard_common.log import get_logger

log = get_logger(__name__)


def bootstrap() -> str:
    return os.getenv("BROKER_BOOTSTRAP", "localhost:19092")


def make_producer(**overrides: Any) -> Producer:
    conf = {
        "bootstrap.servers": bootstrap(),
        "logger": log,  # librdkafka's own logs go through our JSON logging
        "on_delivery": _report_failed_delivery,
        "linger.ms": 5,  # small batching window: throughput without hurting p95
        "compression.type": "lz4",
        "enable.idempotence": True,  # no duplicates from producer retries
        "acks": "all",
    }
    conf.update(overrides)
    return Producer(conf)


def make_consumer(group_id: str, topic_list: list[str], **overrides: Any) -> Consumer:
    conf = {
        "bootstrap.servers": bootstrap(),
        "logger": log,
        "group.id": group_id,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
        "partition.assignment.strategy": "cooperative-sticky",  # less pause when an instance joins/leaves
        # A dead instance keeps its partitions until its session expires. The librdkafka default (45 s)
        # stalled those partitions for 44 s in test RT-01. Heartbeats run on librdkafka's own thread,
        # so a busy Python loop does not trigger a false timeout.
        "session.timeout.ms": 10_000,
        "heartbeat.interval.ms": 3_000,
    }
    conf.update(overrides)
    consumer = Consumer(conf)
    consumer.subscribe(topic_list)
    return consumer


def ensure_topics(timeout: float = 30.0) -> None:
    admin = AdminClient({"bootstrap.servers": bootstrap(), "logger": log})
    existing = set(admin.list_topics(timeout=timeout).topics)
    missing = [
        NewTopic(name, num_partitions=partitions, replication_factor=1)
        for name, partitions in topics.PARTITIONS.items()
        if name not in existing
    ]
    if not missing:
        return
    for name, future in admin.create_topics(missing).items():
        try:
            future.result()
            log.info("topic created", extra={"topic": name})
        except Exception as e:  # already exists (race with another instance) is fine
            log.warning("topic create failed", extra={"topic": name, "error": str(e)})


def encode(msg: dict[str, Any]) -> bytes:
    return json.dumps(msg, separators=(",", ":")).encode()


def poll_batch(consumer: Consumer, max_messages: int = 500, timeout: float = 0.2) -> Iterator[tuple[Message, dict]]:
    """Yield (raw_message, decoded_json). Undecodable messages are logged and skipped."""
    for m in consumer.consume(num_messages=max_messages, timeout=timeout):
        if m.error():
            if m.error().code() != KafkaError._PARTITION_EOF:
                log.error("consumer error", extra={"error": str(m.error())})
            continue
        try:
            payload = json.loads(m.value())
        except (ValueError, TypeError) as e:
            log.error("bad json", extra={"topic": m.topic(), "offset": m.offset(), "error": str(e)})
            continue
        yield m, payload


def _report_failed_delivery(err: KafkaError | None, msg: Message) -> None:
    # Called from producer.poll()/flush(). Without it a message lost after all retries disappears silently.
    if err is not None:
        log.error("message not delivered", extra={"topic": msg.topic(), "error": str(err)})
