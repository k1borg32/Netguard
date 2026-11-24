"""The fast flow check of the importer gives the same answer as the JSON schema (UT-26, NFR01).

The importer checks every flow. The schema check (jsonschema) is the single source of truth but slow, so the importer
first runs `flow_is_valid_fast` and asks the schema only when that is not sure. Two rules are tested here:
  1. the fast check never accepts a flow the schema rejects (a wrong "yes" would let a bad flow into the broker),
  2. a flow that the fast check does not accept still gets exactly the rejection reason of the schema.
"""

import importlib
import pathlib
import random
import sys
import uuid

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "services" / "importer"))
importer = importlib.import_module("importer")
messages = importlib.import_module("netguard_common.messages")


def good_flow(**changes) -> dict:
    flow = {
        "schema_version": 1,
        "flow_id": str(uuid.uuid5(messages.NETGUARD_NS, "x#1")),
        "trace_id": "0" * 32,
        "ingested_at": 1_700_000_000.5,
        "ts_start": 1_700_000_000.0,
        "duration_ms": 12.5,
        "src_ip": "10.0.0.1",
        "dst_ip": "2001:db8::1",
        "src_port": 40000,
        "dst_port": 443,
        "protocol": "TCP",
        "packets": 3,
        "bytes": 180,
        "tcp_flags": "SA",
        "label": None,
        "source": "flowfile",
    }
    flow.update(changes)
    return flow


def schema_says_valid(flow) -> bool:
    try:
        messages.validate_flow(flow)
    except messages.SchemaError:
        return False
    return True


BAD_VALUES = {
    "schema_version": [2, "1", True, 1.0, None],
    "flow_id": ["", "not-a-uuid", 5, None, "6F1D2C1E-5B0A-4F3E-9D7A-0E7C1B2A3C4D", "6f1d2c1e5b0a4f3e9d7a0e7c1b2a3c4d"],
    "trace_id": ["short", "x" * 65, 12345678, None],
    "ingested_at": ["1.0", None, True, [1]],
    "ts_start": ["1.0", None, False, {}],
    "duration_ms": [-1, -0.001, "5", None, True, float("nan")],
    "src_ip": ["", "300.1.1.1", "10.0.0", "fe80::1%eth0", 5, None, "01.2.3.4", "1.2.3.4 ", ["1.2.3.4"]],
    "dst_ip": ["", "::g", None, 4],
    "src_port": [-1, 65536, 80.0, 80.5, "80", None, True],
    "dst_port": [-1, 65536, 1e3, None, False],
    "protocol": ["tcp", "SCTP", "", None, 6, ["TCP"], {}],
    "packets": [-1, 1.0, 1.5, "1", None, True],
    "bytes": [-1, 2.0, "x", None],
    "tcp_flags": ["x", "sa", "S A", 5, ["S"], ""],
    "label": ["Normal", "attack", "", 3, ["dos"], {}],
    "source": ["file", "", None, 1, ["pcap"]],
}


def test_a_normal_flow_is_accepted_by_the_fast_check_and_by_the_schema():
    for flow in (good_flow(), good_flow(label="port_scan", tcp_flags=None), good_flow(protocol="UDP", tcp_flags=None)):
        assert importer.flow_is_valid_fast(flow) is True
        assert schema_says_valid(flow) is True
        importer.check_flow(flow)


@pytest.mark.parametrize("field", sorted(BAD_VALUES))
def test_fast_check_never_accepts_what_the_schema_rejects(field):
    for value in BAD_VALUES[field]:
        flow = good_flow(**{field: value})
        if importer.flow_is_valid_fast(flow):
            assert schema_says_valid(flow), f"{field}={value!r}: fast check says valid, the schema does not"


@pytest.mark.parametrize("field", sorted(BAD_VALUES))
def test_rejection_reason_is_the_one_of_the_schema(field):
    for value in BAD_VALUES[field]:
        flow = good_flow(**{field: value})
        if schema_says_valid(flow):
            importer.check_flow(flow)  # unusual but valid (for example 1.0 as an integer): must pass
            continue
        with pytest.raises(messages.SchemaError) as fast:
            importer.check_flow(flow)
        with pytest.raises(messages.SchemaError) as slow:
            messages.validate_flow(flow)
        assert str(fast.value) == str(slow.value)


def test_missing_and_extra_fields():
    required = [k for k in good_flow() if k not in ("tcp_flags", "label")]
    for key in required:
        flow = good_flow()
        del flow[key]
        assert importer.flow_is_valid_fast(flow) is False
        assert schema_says_valid(flow) is False
    for flow in (good_flow(extra=1), good_flow(Label="x")):
        assert importer.flow_is_valid_fast(flow) is False
        assert schema_says_valid(flow) is False
    optional_left_out = good_flow()
    del optional_left_out["tcp_flags"], optional_left_out["label"]
    assert importer.flow_is_valid_fast(optional_left_out) is True
    assert schema_says_valid(optional_left_out) is True


def test_random_flows_fast_check_agrees_with_the_schema():
    """A seeded fuzz: 5,000 flows with one to three random changes. Rule 1 must hold for every one of them."""
    rng = random.Random(7)
    junk = [None, True, False, 0, -1, 1, 65535, 65536, 1.0, 2.5, "", "a", "10.0.0.1", "::1", "TCP", [], {}, "S", 1e18]
    fields = list(good_flow())
    accepted_by_fast = 0
    for _ in range(5000):
        flow = good_flow()
        for _ in range(rng.randint(1, 3)):
            field = rng.choice(fields)
            action = rng.random()
            if action < 0.15:
                flow.pop(field, None)
            elif action < 0.25:
                flow[f"x{rng.randint(0, 3)}"] = rng.choice(junk)
            else:
                flow[field] = rng.choice(junk + BAD_VALUES.get(field, []))
        if importer.flow_is_valid_fast(flow):
            accepted_by_fast += 1
            assert schema_says_valid(flow), flow
    assert accepted_by_fast > 0  # the fuzz must not only produce bad flows
