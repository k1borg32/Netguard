"""Classify API tests by directory; integration fixtures stay in integration/."""

from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if not item.path.is_relative_to(TESTS_DIR):
            continue
        directory = item.path.relative_to(TESTS_DIR).parts[0]
        if directory in {"unit", "integration"}:
            item.add_marker(getattr(pytest.mark, directory))
