"""Async PostgreSQL engine and request-scoped database sessions."""

from collections.abc import AsyncIterator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.config import Settings

database_url = make_url(str(Settings().database_url))
# Compose supplies a plain PostgreSQL URL; select the existing psycopg driver.
if database_url.drivername in {"postgres", "postgresql"}:
    database_url = database_url.set(drivername="postgresql+psycopg")

engine = create_async_engine(database_url, native_inet_types=False)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session for FastAPI Depends; callers explicitly commit writes."""
    async with session_factory() as session:
        yield session
