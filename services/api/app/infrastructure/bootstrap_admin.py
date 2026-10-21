"""Create the first administrator using an interactive terminal, never an HTTP request."""

import getpass
import sys

import psycopg
from psycopg.errors import UniqueViolation
from pydantic import ValidationError

from app.domain.user import User
from app.domain.user_role import UserRole
from app.infrastructure.config import database_dsn
from app.infrastructure.security.password_hasher import Argon2PasswordHasher


def create_initial_admin(connection: psycopg.Connection, username: str, password_hash: str) -> None:
    user = User(username=username, password_hash=password_hash, role=UserRole.ADMIN)
    with connection.transaction():
        # Serialize bootstrap invocations and block concurrent user changes until commit.
        with connection.cursor() as cursor:
            cursor.execute("LOCK TABLE users IN EXCLUSIVE MODE")
            cursor.execute("SELECT 1 FROM users WHERE role = %s LIMIT 1", (UserRole.ADMIN.value,))
            if cursor.fetchone() is not None:
                raise ValueError("An administrator already exists")
            try:
                cursor.execute(
                    "INSERT INTO users (user_id, username, password_hash, role) VALUES (%s, %s, %s, %s)",
                    (user.user_id, user.username, user.password_hash, user.role.value),
                )
            except UniqueViolation:
                raise ValueError("Username already exists") from None


def main() -> int:
    try:
        username = input("Login administratora: ")
        password = getpass.getpass("Hasło (minimum 12 znaków): ")
        if password != getpass.getpass("Powtórz hasło: "):
            print("Hasła są różne.", file=sys.stderr)
            return 1
        if not 12 <= len(password) <= 1024:
            raise ValueError("Hasło musi mieć 12-1024 znaków")
        password_hash = Argon2PasswordHasher().hash(password)
        with psycopg.connect(database_dsn(), autocommit=True, connect_timeout=5) as connection:
            create_initial_admin(connection, username, password_hash)
    except ValidationError:
        print("Nieprawidłowa konfiguracja środowiska.", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except psycopg.Error:
        print("Nie można utworzyć administratora. Sprawdź bazę i konfigurację.", file=sys.stderr)
        return 1
    print("Utworzono administratora.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
