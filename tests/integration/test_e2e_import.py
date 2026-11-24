"""A known attack from an imported file to the detection, through the running stack (`make up`, then `make test-stack`).

The same scan as in the committed test files (data/pcap/portscan-small.pcap, data/flows/scan-small.csv), but with an
attacker address that is new in every run: the detection of an earlier run can't make the test pass by mistake.
The processor closes the last window of a source that went quiet by the wall clock, so the detection comes about
10 to 20 s after the import.
"""

import importlib
import sys
import time
import uuid
from pathlib import Path

import pytest

from netguard_common import flow_id_for

pytestmark = [pytest.mark.integration, pytest.mark.stack]

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "importer"))
fixtures = importlib.import_module("make_scan_fixtures")

DETECTION_TIMEOUT_S = 90


def new_attacker() -> str:
    n = uuid.uuid4().int
    return f"10.99.{n % 250 + 1}.{(n // 250) % 250 + 1}"


def stored(db, file: Path, count: int, source: str) -> int:
    ids = [flow_id_for(file.name, index) for index in range(count)]
    query = "SELECT count(*) FROM network_flows WHERE flow_id = ANY(%s::uuid[]) AND source = %s"
    return db.execute(query, (ids, source)).fetchone()[0]


def detection_types(db, attacker: str) -> set[str]:
    rows = db.execute("SELECT type FROM detections WHERE host(src_ip) = %s", (attacker,)).fetchall()
    return {r[0] for r in rows}


@pytest.mark.parametrize(
    ("name", "write", "source"),
    [("scan.pcap", fixtures.write_pcap, "pcap"), ("scan.csv", fixtures.write_csv, "flowfile")],
)
def test_port_scan_file_ends_as_a_detection(name, write, source, run_importer, import_dir, stack_db):
    """IT-09 (input of ST-02 and ST-03): all flows are stored with their source and the scan is detected."""
    attacker = new_attacker()
    file = import_dir / name
    flows = write(file, attacker)

    result = run_importer(file)

    assert result.returncode == 0, result.stdout
    assert f"accepted={flows} rejected=0" in result.stdout, result.stdout
    deadline = time.time() + DETECTION_TIMEOUT_S
    while time.time() < deadline and "port_scan" not in detection_types(stack_db, attacker):
        time.sleep(2)
    assert stored(stack_db, file, flows, source) == flows
    assert "port_scan" in detection_types(stack_db, attacker), f"no port_scan detection for {attacker}"
