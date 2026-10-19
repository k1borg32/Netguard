"""Request-scoped database connections and repository bindings."""

from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends

from app.abstraction.auth.ports import AuthRepository
from app.features.auth.exceptions import AuthStorageError
from app.infrastructure.config import database_dsn
from app.infrastructure.repo.auth_repository import PsycopgAuthRepository


def get_db_connection() -> Iterator[psycopg.Connection]:
    try:
        with psycopg.connect(database_dsn(), autocommit=True, connect_timeout=5) as connection:
            yield connection
    except psycopg.Error:
        raise AuthStorageError() from None


def get_auth_repository(connection: Annotated[psycopg.Connection, Depends(get_db_connection)]) -> AuthRepository:
    return PsycopgAuthRepository(connection)


Repository = Annotated[AuthRepository, Depends(get_auth_repository)]
