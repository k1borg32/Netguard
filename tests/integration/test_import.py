"""Importing PCAP and flow files into the running stack (`make up`, then `make test-stack`).

The importer runs in its own container, like `make import`. Flow IDs come from the file name and the record number,
so every test imports a copy of a sample under a new name: the rows it checks are its own, even in a database that
already holds earlier runs.
"""

import re
import shutil
import time
from pathlib import Path

import pytest

from netguard_common import flow_id_for

pytestmark = [pytest.mark.integration, pytest.mark.stack]

DATA = Path(__file__).resolve().parents[2] / "data"
SUMMARY = re.compile(r"accepted=(\d+) rejected=(\d+)")
SAMPLE_PCAP = (DATA / "pcap/sample.pcap").read_bytes()
NOT_REJECTED_YET = pytest.mark.xfail(strict=True, reason="the importer doesn't reject broken captures yet (#51)")


def summary(result) -> tuple[int, int]:
    match = SUMMARY.search(result.stdout)
    assert match, f"no import summary in the output:\n{result.stdout}"
    return int(match.group(1)), int(match.group(2))


def copy_sample(sample: str, folder: Path) -> Path:
    file = folder / f"{folder.name}-{Path(sample).name}"
    shutil.copy(DATA / sample, file)
    return file


def stored_flows(db, file: Path, count: int, source: str) -> int:
    ids = [flow_id_for(file.name, index) for index in range(count)]
    query = "SELECT count(*) FROM network_flows WHERE flow_id = ANY(%s::uuid[]) AND source = %s"
    return db.execute(query, (ids, source)).fetchone()[0]


def wait_until_stored(db, file: Path, count: int, source: str, timeout_s: float = 30) -> int:
    deadline = time.time() + timeout_s
    while (found := stored_flows(db, file, count, source)) < count and time.time() < deadline:
        time.sleep(1)
    return found


def pcap_rows(db) -> int:
    return db.execute("SELECT count(*) FROM network_flows WHERE source = 'pcap'").fetchone()[0]


@pytest.mark.parametrize("sample,source", [("pcap/sample.pcap", "pcap"), ("flows/sample.csv", "flowfile")])
def test_imported_file_is_stored(sample, source, run_importer, import_dir, stack_db):
    """IT-03: every flow of the file goes through the broker into the database, with its source."""
    file = copy_sample(sample, import_dir)

    result = run_importer(file)

    assert result.returncode == 0, result.stdout
    accepted, rejected = summary(result)
    assert accepted > 0 and rejected == 0
    assert wait_until_stored(stack_db, file, accepted, source) == accepted


def test_same_file_imported_twice_is_stored_once(run_importer, import_dir, stack_db):
    """IT-05: deterministic flow IDs + the primary key, so a second import of a file adds no rows."""
    file = copy_sample("pcap/sample.pcap", import_dir)
    before = pcap_rows(stack_db)

    first, second = run_importer(file), run_importer(file)

    assert first.returncode == second.returncode == 0, first.stdout + second.stdout
    accepted = summary(first)[0]
    assert summary(second)[0] == accepted
    assert wait_until_stored(stack_db, file, accepted, "pcap") == accepted
    # The second copy of each flow is behind the first one on the broker. Give the persister a few batches
    # (it writes every 0.5 s) and check that the row count doesn't move.
    deadline = time.time() + 5
    while time.time() < deadline:
        assert pcap_rows(stack_db) == before + accepted
        time.sleep(1)


@pytest.mark.parametrize(
    "name,content",
    [
        pytest.param("not-a-capture.pcap", b"this is not a capture\n", marks=NOT_REJECTED_YET, id="not-a-capture"),
        pytest.param("empty.pcap", b"", marks=NOT_REJECTED_YET, id="empty"),
        pytest.param("truncated.pcap", SAMPLE_PCAP[:300], marks=NOT_REJECTED_YET, id="truncated"),
    ],
)
def test_broken_capture_is_rejected(name, content, run_importer, import_dir):
    """SEC-02: a capture that can't be read completely is rejected with the reason, without a crash."""
    file = import_dir / name
    file.write_bytes(content)

    result = run_importer(file)

    assert "Traceback" not in result.stdout, result.stdout
    assert result.returncode != 0, result.stdout
    assert re.search("reject", result.stdout, re.IGNORECASE), result.stdout


def test_invalid_rows_are_rejected_and_the_rest_is_imported(run_importer, import_dir):
    """SEC-02: invalid records are rejected with their reason, the valid ones are still published."""
    header, *rows = (DATA / "flows/sample.csv").read_text(encoding="utf-8").splitlines()
    valid = rows[:2]
    invalid = [
        "1700000000.0,30.0,10.0.0.5,not-an-ip,51514,443,6,12,1840,SA,normal",
        "1700000000.0,30.0,10.0.0.5,10.0.0.9,51514,99999,6,12,1840,SA,normal",
        "1700000000.0,30.0,10.0.0.5,10.0.0.9,51514,443,6,12,1840,SA,evil",
    ]
    file = import_dir / "invalid-rows.csv"
    file.write_text("\n".join([header, *valid, *invalid]) + "\n", encoding="utf-8")

    result = run_importer(file)

    assert "Traceback" not in result.stdout, result.stdout
    assert result.returncode == 0, result.stdout
    assert summary(result) == (len(valid), len(invalid))
