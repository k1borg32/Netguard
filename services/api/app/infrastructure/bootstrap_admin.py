"""Create the first administrator using an interactive terminal, never an HTTP request."""

import getpass
import sys

import psycopg
from pydantic import ValidationError

from app.abstraction.auth.enums import UserRole
from app.features.auth.register.request import RegisterRequest
from app.features.common.app_exception import AppException
from app.infrastructure.config import database_dsn
from app.infrastructure.repo.auth_repository import PsycopgAuthRepository
from app.infrastructure.security.password_hasher import Argon2PasswordHasher


def create_initial_admin(connection: psycopg.Connection, username: str, password_hash: str) -> None:
    with connection.transaction():
        # Serialize bootstrap invocations and block concurrent user changes until commit.
        with connection.cursor() as cursor:
            cursor.execute("LOCK TABLE users IN EXCLUSIVE MODE")
            cursor.execute("SELECT 1 FROM users WHERE role = %s LIMIT 1", (UserRole.ADMIN.value,))
            if cursor.fetchone() is not None:
                raise AppException(409, "An administrator already exists")
        PsycopgAuthRepository(connection).create_user(username, password_hash, UserRole.ADMIN)


def main() -> int:
    try:
        username = input("Login administratora: ")
        password = getpass.getpass("Hasło (minimum 12 znaków): ")
        if password != getpass.getpass("Powtórz hasło: "):
            print("Hasła są różne.", file=sys.stderr)
            return 1
        request = RegisterRequest(username=username, password=password, role=UserRole.ADMIN)
        password_hash = Argon2PasswordHasher().hash(request.password)
        with psycopg.connect(database_dsn(), autocommit=True, connect_timeout=5) as connection:
            create_initial_admin(connection, request.username, password_hash)
    except ValidationError:
        print("Nieprawidłowy login lub hasło (minimum 12, maksimum 1024 znaków).", file=sys.stderr)
        return 1
    except AppException as exc:
        print(exc.message, file=sys.stderr)
        return 1
    except psycopg.Error:
        print("Nie można utworzyć administratora. Sprawdź bazę i konfigurację.", file=sys.stderr)
        return 1
    print("Utworzono administratora.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
