"""Real API and disposable local TimescaleDB, without dependency overrides."""

import os
import secrets
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from app.abstraction.auth.enums import UserRole
from app.abstraction.auth.models import AuthUser
from app.infrastructure.repo.auth_repository import PsycopgAuthRepository
from app.infrastructure.security.password_hasher import Argon2PasswordHasher
from fastapi.testclient import TestClient
from psycopg import sql

ROOT_DIR = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Own a unique Compose project, random port and ephemeral database storage."""
    password = secrets.token_hex(24)
    environment = {**os.environ, "NETGUARD_TEST_DB_PASSWORD": password}
    command = [
        "docker",
        "compose",
        "--project-name",
        f"netguard-tests-{uuid4().hex[:12]}",
        "--file",
        str(ROOT_DIR / "docker-compose.test.yml"),
    ]

    def compose(*arguments: str) -> str:
        try:
            result = subprocess.run(
                [*command, *arguments],
                cwd=ROOT_DIR,
                env=environment,
                capture_output=True,
                text=True,
                timeout=180,
                check=True,
            )
        except FileNotFoundError:
            pytest.fail("Integration tests require Docker Compose. Install and start Docker Desktop.")
        except subprocess.TimeoutExpired:
            pytest.fail("Test database operation timed out. Check Docker Desktop.")
        except subprocess.CalledProcessError as exc:
            pytest.fail(f"Test database operation failed:\n{exc.stdout}\n{exc.stderr}")
        return result.stdout.strip()

    try:
        compose("up", "--detach", "--wait", "--wait-timeout", "120", "db")
        endpoint = compose("port", "db", "5432")
        host, port = endpoint.rsplit(":", 1)
        if host != "127.0.0.1":
            pytest.fail(f"Expected a local test database, received {endpoint!r}.")
        yield f"postgresql://netguard_test:{password}@{host}:{int(port)}/netguard_test"
    finally:
        compose("down", "--volumes", "--remove-orphans")


@pytest.fixture(scope="session")
def api_environment(database_url: str) -> Iterator[None]:
    """Configure real dependencies before importing the application."""
    values = {"DATABASE_URL": database_url, "JWT_SECRET": secrets.token_hex(32)}
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    from app.di.security import get_auth, get_dummy_password_hash, get_password_hasher

    caches = (get_auth, get_dummy_password_hash, get_password_hasher)
    for provider in caches:
        provider.cache_clear()
    try:
        yield
    finally:
        for provider in caches:
            provider.cache_clear()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(autouse=True)
def db(database_url: str, api_environment: None) -> Iterator[psycopg.Connection]:
    """Truncate all application tables before and after every integration test.

    Requests commit using their own connections, so a test-level rollback would
    not isolate tests. The URL always belongs to the disposable Compose project.
    """
    with psycopg.connect(database_url, autocommit=True, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
            tables = [sql.Identifier("public", row[0]) for row in cursor.fetchall()]
        if not tables:
            pytest.fail("The test database has no application tables. Check db/init SQL scripts.")
        truncate = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(sql.SQL(", ").join(tables))
        connection.execute(truncate)
        try:
            yield connection
        finally:
            # A test may have failed inside an explicit transaction.
            connection.rollback()
            connection.execute(truncate)


@pytest.fixture
def client(db: psycopg.Connection) -> Iterator[TestClient]:
    from app.app import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def create_user(db: psycopg.Connection) -> Callable[..., AuthUser]:
    """Seed accounts through the real repository and Argon2 password hasher."""
    repository = PsycopgAuthRepository(db)
    hasher = Argon2PasswordHasher()

    def create(
        username: str = "test-user",
        password: str = "test-password-12345",
        role: UserRole = UserRole.USER,
    ) -> AuthUser:
        return repository.create_user(username, hasher.hash(password), role)

    return create
