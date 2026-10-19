"""Authentication persistence using the existing psycopg driver and database URL."""

from datetime import datetime
from hashlib import sha256
from typing import cast
from uuid import UUID, uuid4

from app.abstraction.auth.enums import UserRole
from app.abstraction.auth.models import AuthUser
from app.features.auth.exceptions import UserAlreadyExistsError
from psycopg import Connection
from psycopg.errors import UniqueViolation


class PsycopgAuthRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    @staticmethod
    def _user(row: tuple | None) -> AuthUser | None:
        if row is None:
            return None
        return AuthUser(
            user_id=cast(UUID, row[0]),
            username=cast(str, row[1]),
            password_hash=cast(str, row[2]),
            role=UserRole(row[3]),
        )

    def find_by_username(self, username: str) -> AuthUser | None:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT user_id, username, password_hash, role FROM users WHERE username = %s", (username,))
            return self._user(cursor.fetchone())

    def find_by_id(self, user_id: UUID) -> AuthUser | None:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT user_id, username, password_hash, role FROM users WHERE user_id = %s", (user_id,))
            return self._user(cursor.fetchone())

    def create_user(self, username: str, password_hash: str, role: UserRole) -> AuthUser:
        user = AuthUser(uuid4(), username, password_hash, role)
        try:
            with self._connection.transaction(), self._connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (user_id, username, password_hash, role) VALUES (%s, %s, %s, %s)",
                    (user.user_id, user.username, user.password_hash, user.role.value),
                )
        except UniqueViolation:
            raise UserAlreadyExistsError() from None
        return user

    @staticmethod
    def _digest(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def save_refresh_token(self, user_id: UUID, token: str, expires_at: datetime) -> None:
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO auth_refresh_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                (self._digest(token), user_id, expires_at),
            )

    def rotate_refresh_token(self, user_id: UUID, old_token: str, new_token: str, expires_at: datetime) -> bool:
        with self._connection.transaction(), self._connection.cursor() as cursor:
            # DELETE locks the matching row. Concurrent requests recheck after the winner commits.
            cursor.execute(
                "DELETE FROM auth_refresh_sessions WHERE token_hash = %s AND user_id = %s "
                "AND expires_at > clock_timestamp() RETURNING user_id",
                (self._digest(old_token), user_id),
            )
            if cursor.fetchone() is None:
                return False
            cursor.execute(
                "INSERT INTO auth_refresh_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                (self._digest(new_token), user_id, expires_at),
            )
        return True

    def revoke_refresh_token(self, user_id: UUID, token: str) -> bool:
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM auth_refresh_sessions WHERE token_hash = %s AND user_id = %s "
                "AND expires_at > clock_timestamp() RETURNING user_id",
                (self._digest(token), user_id),
            )
            return cursor.fetchone() is not None
