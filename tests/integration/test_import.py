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
PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"


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


def assert_rejected(result) -> None:
    """The whole file is rejected: exit code 1, nothing imported, the reason in the summary and no crash."""
    assert "Traceback" not in result.stdout, result.stdout
    assert result.returncode == 1, result.stdout
    assert summary(result) == (0, 0)
    assert "error=None" not in result.stdout, result.stdout


@pytest.mark.parametrize(
    "name,content",
    [
        pytest.param("not-a-capture.pcap", b"this is not a capture\n", id="not-a-capture"),
        pytest.param("empty.pcap", b"", id="empty"),
        pytest.param("capture.pcapng", PCAPNG_MAGIC + bytes(28), id="pcapng"),
        pytest.param("flows.txt", b"just some text\n", id="unsupported-type"),
    ],
)
def test_unreadable_file_is_rejected(name, content, run_importer, import_dir):
    """SEC-02: a file that can't be imported is rejected with the reason, without a crash."""
    file = import_dir / name
    file.write_bytes(content)

    assert_rejected(run_importer(file))


def test_oversized_capture_is_rejected(run_importer, import_dir):
    """SEC-02: a capture over the size limit is rejected before it is read (the PCAP path keeps flows in memory)."""
    file = copy_sample("pcap/sample.pcap", import_dir)

    assert_rejected(run_importer(file, MAX_PCAP_MB="0"))


def test_truncated_capture_is_imported_with_a_warning(run_importer, import_dir):
    """SEC-02: the complete packets of a truncated capture are imported and the summary says it was truncated."""
    file = import_dir / "truncated.pcap"
    file.write_bytes(SAMPLE_PCAP[:300])

    result = run_importer(file)

    assert "Traceback" not in result.stdout, result.stdout
    assert result.returncode == 0, result.stdout
    assert summary(result)[0] > 0
    assert "truncated" in result.stdout


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
