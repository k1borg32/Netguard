import json
import logging

from netguard_common import get_logger, setup_logging, trace_context


def test_log_lines_are_json_with_trace_id(capsys):
    setup_logging("test-svc")
    log = get_logger("t")
    with trace_context("trace-123"):
        log.info("hello", extra={"src_ip": "10.0.0.1"})
    log.info("outside")
    lines = [json.loads(x) for x in capsys.readouterr().out.strip().splitlines()]
    assert lines[0]["trace_id"] == "trace-123"
    assert lines[0]["service"] == "test-svc"
    assert lines[0]["src_ip"] == "10.0.0.1"
    assert lines[1]["trace_id"] is None
    logging.getLogger().handlers.clear()
