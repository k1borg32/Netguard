"""Repository-wide test policy: run test cases sequentially."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    workers = getattr(config.option, "numprocesses", None)
    if workers not in (None, 0, "0") or hasattr(config, "workerinput"):
        raise pytest.UsageError("Tests run sequentially. Remove -n/--numprocesses or use -n 0.")
