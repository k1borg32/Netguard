import copy

import pytest

from netguard_common import SchemaError, validate_manifest

MANIFEST = {
    "schema_version": 1,
    "dataset": "SIM-SCEN",
    "source": "simulator",
    "seed": 42,
    "created_at": 1760000600.0,
    "episodes": [
        {
            "episode_id": "port_scan-001",
            "class": "port_scan",
            "attackers": ["10.66.6.6"],
            "targets": ["10.1.0.1"],
            "start": 1760000000.0,
            "end": 1760000030.0,
            "params": {"ports": 300, "rate_per_s": 10},
        },
        {
            "episode_id": "dos-001",
            "class": "dos",
            "attackers": ["10.77.0.0/24"],
            "targets": ["10.1.0.5"],
            "start": 1760000100.0,
            "end": 1760000160.0,
        },
    ],
}


def test_valid_manifest_passes():
    """UT-19"""
    assert validate_manifest(copy.deepcopy(MANIFEST))


def test_pcap_manifest_without_seed_passes():
    """UT-19"""
    validate_manifest({**MANIFEST, "source": "pcap", "seed": None, "notes": "checked by a second person"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("class", "normal"),
        ("class", "unknown"),
        ("attackers", []),
        ("start", "yesterday"),
    ],
)
def test_invalid_episode_rejected(field, value):
    """UT-19"""
    m = copy.deepcopy(MANIFEST)
    m["episodes"][0][field] = value
    with pytest.raises(SchemaError, match=field):
        validate_manifest(m)


def test_episode_ending_before_start_rejected():
    """UT-19"""
    m = copy.deepcopy(MANIFEST)
    m["episodes"][0]["end"] = m["episodes"][0]["start"] - 1
    with pytest.raises(SchemaError, match="end is before start"):
        validate_manifest(m)


def test_duplicate_episode_ids_rejected():
    """UT-19"""
    m = copy.deepcopy(MANIFEST)
    m["episodes"][1]["episode_id"] = m["episodes"][0]["episode_id"]
    with pytest.raises(SchemaError, match="unique"):
        validate_manifest(m)
