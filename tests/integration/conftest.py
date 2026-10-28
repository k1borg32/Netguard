"""Fixtures for the full-stack tests: the stack database and the importer container."""

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "--profile", "import"]


def stack_db_settings() -> dict:
    """Credentials of the running stack from .env, the same file Compose uses."""
    env = {}
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                env[key.strip()] = value.strip()
    return {
        "host": "127.0.0.1",
        "port": 5432,
        "user": env.get("POSTGRES_USER", "netguard"),
        "password": env.get("POSTGRES_PASSWORD", ""),
        "dbname": env.get("POSTGRES_DB", "netguard"),
    }


@pytest.fixture(scope="session")
def stack_db():
    conninfo = os.getenv("STACK_DATABASE_URL", "")
    with psycopg.connect(conninfo, autocommit=True, **({} if conninfo else stack_db_settings())) as connection:
        yield connection


@pytest.fixture(scope="session")
def run_importer():
    """Runs the importer container like `make import` on a file inside data/ and returns the finished process."""
    build = subprocess.run(
        [*COMPOSE, "build", "importer"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    if build.returncode != 0:
        pytest.fail(f"importer image did not build:\n{build.stdout}\n{build.stderr}")

    def run(file: Path, **env: str) -> subprocess.CompletedProcess:
        settings = {"FLOW_FILE": "/app/" + file.relative_to(ROOT).as_posix(), **env}
        env_args = [arg for key, value in settings.items() for arg in ("-e", f"{key}={value}")]
        return subprocess.run(
            [*COMPOSE, "run", "--rm", "--no-deps", "-T", *env_args, "importer"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

    return run


@pytest.fixture
def import_dir():
    """A fresh folder under data/, which Compose mounts into the importer container. Removed after the test."""
    folder = ROOT / "data" / "tmp" / uuid.uuid4().hex[:8]
    folder.mkdir(parents=True)
    yield folder
    shutil.rmtree(folder, ignore_errors=True)
