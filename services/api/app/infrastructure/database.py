"""One async SQLAlchemy session per request; handlers commit their writes."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.config import Settings
from app.infrastructure.persistence.mappings import configure_mappings


@lru_cache
def get_engine() -> AsyncEngine:
    database_url = make_url(Settings().database_url)
    if database_url.drivername in {"postgres", "postgresql"}:
        database_url = database_url.set(drivername="postgresql+psycopg")
    return create_async_engine(
        database_url,
        native_inet_types=False,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    configure_mappings()
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
