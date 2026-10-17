"""Settings and session lifecycle checks without a database server."""

import asyncio
import importlib
from unittest.mock import AsyncMock

import pytest
from app.infrastructure.config import Settings
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_database_url_is_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/netguard")
    assert Settings().database_url.hosts()[0]["host"] == "localhost"


def test_database_url_rejects_other_database_types(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///netguard.db")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("fail_request", [False, True])
def test_session_dependency_closes_session_without_connecting(monkeypatch, fail_request):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/netguard")
    database = importlib.import_module("app.infrastructure.database")
    assert database.engine.dialect.is_async
    assert database.engine.url.drivername == "postgresql+psycopg"
    assert database.engine.dialect._native_inet_types is False

    async def check_lifecycle():
        connect = AsyncMock(side_effect=AssertionError("Database connection attempted"))
        monkeypatch.setattr(database.engine.sync_engine, "connect", connect)
        dependency = database.get_db_session()
        session = await anext(dependency)
        assert isinstance(session, AsyncSession)
        close = AsyncMock(wraps=session.close)
        commit = AsyncMock()
        monkeypatch.setattr(session, "close", close)
        monkeypatch.setattr(session, "commit", commit)
        if fail_request:
            with pytest.raises(RuntimeError, match="Request failed"):
                await dependency.athrow(RuntimeError("Request failed"))
        else:
            with pytest.raises(StopAsyncIteration):
                await anext(dependency)
        close.assert_awaited_once()
        commit.assert_not_awaited()
        connect.assert_not_called()
        await database.engine.dispose()

    asyncio.run(check_lifecycle())
