"""poll_batch must never let one bad message stop a consumer."""

from confluent_kafka import KafkaError

from netguard_common.broker import poll_batch


class FakeMessage:
    def __init__(self, value: bytes, error: KafkaError | None = None):
        self._value = value
        self._error = error

    def value(self) -> bytes:
        return self._value

    def error(self) -> KafkaError | None:
        return self._error

    def topic(self) -> str:
        return "flows.raw"

    def offset(self) -> int:
        return 0


class FakeConsumer:
    def __init__(self, messages: list[FakeMessage]):
        self.messages = messages

    def consume(self, num_messages: int, timeout: float) -> list[FakeMessage]:
        return self.messages


def test_poll_batch_skips_bad_messages():
    """UT-10"""
    consumer = FakeConsumer([
        FakeMessage(b'{"n": 1}'),
        FakeMessage(b"not json {"),
        FakeMessage(b"", error=KafkaError(KafkaError._PARTITION_EOF)),
        FakeMessage(b'{"n": 2}'),
    ])  # fmt: skip

    payloads = [payload for _, payload in poll_batch(consumer)]

    assert payloads == [{"n": 1}, {"n": 2}]
