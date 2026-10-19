"""HTTP -> controller -> handler -> real security and PostgreSQL -> response."""

from hashlib import sha256

import psycopg
import pytest
from app.abstraction.auth.enums import UserRole
from app.infrastructure.security.password_hasher import Argon2PasswordHasher
from fastapi.testclient import TestClient

PASSWORD = "test-password-12345"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_refresh_logout_flow(client: TestClient, db: psycopg.Connection, create_user) -> None:
    create_user(username="admin", role=UserRole.ADMIN)
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert admin_login.status_code == 200, admin_login.text

    registration = client.post(
        "/api/v1/auth/register",
        headers=bearer(admin_login.json()["access_token"]),
        json={"username": "alice", "password": PASSWORD},
    )
    assert registration.status_code == 201, registration.text
    user = registration.json()
    assert user["username"] == "alice"
    assert user["role"] == "user"
    assert "password_hash" not in user
    stored_hash = db.execute("SELECT password_hash FROM users WHERE username = 'alice'").fetchone()[0]
    assert stored_hash != PASSWORD
    assert Argon2PasswordHasher().verify(PASSWORD, stored_hash)

    login = client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
    assert login.status_code == 200, login.text
    tokens = login.json()
    session = db.execute(
        "SELECT token_hash FROM auth_refresh_sessions WHERE user_id = %s", (user["user_id"],)
    ).fetchone()
    assert session == (sha256(tokens["refresh_token"].encode()).hexdigest(),)
    me = client.get("/api/v1/auth/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 200, me.text
    assert me.json() == user

    refreshed = client.post("/api/v1/auth/refresh", headers=bearer(tokens["refresh_token"]))
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert client.post("/api/v1/auth/refresh", headers=bearer(tokens["refresh_token"])).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(new_tokens["access_token"])).json() == user

    logout = client.post("/api/v1/auth/logout", headers=bearer(new_tokens["refresh_token"]))
    assert logout.status_code == 204, logout.text
    assert logout.content == b""
    assert db.execute(
        "SELECT count(*) FROM auth_refresh_sessions WHERE user_id = %s", (user["user_id"],)
    ).fetchone() == (0,)
    assert client.post("/api/v1/auth/refresh", headers=bearer(new_tokens["refresh_token"])).status_code == 401


def test_regular_user_cannot_register_an_account(client: TestClient, db: psycopg.Connection, create_user) -> None:
    create_user()
    login = client.post("/api/v1/auth/login", json={"username": "test-user", "password": PASSWORD})
    assert login.status_code == 200, login.text

    response = client.post(
        "/api/v1/auth/register",
        headers=bearer(login.json()["access_token"]),
        json={"username": "other-user", "password": PASSWORD},
    )

    assert response.status_code == 403
    assert db.execute("SELECT count(*) FROM users").fetchone() == (1,)


def test_anonymous_client_cannot_register_an_account(client: TestClient, db: psycopg.Connection) -> None:
    response = client.post("/api/v1/auth/register", json={"username": "alice", "password": PASSWORD})

    assert response.status_code == 401
    assert db.execute("SELECT count(*) FROM users").fetchone() == (0,)


@pytest.mark.parametrize("password", ["incorrect-password", PASSWORD])
def test_login_rejects_invalid_credentials(client: TestClient, create_user, password: str) -> None:
    create_user()
    username = "test-user" if password != PASSWORD else "missing-user"

    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})

    assert response.status_code == 401


@pytest.mark.parametrize("attempt", [1, 2])
def test_each_test_starts_with_empty_database(
    client: TestClient, db: psycopg.Connection, create_user, attempt: int
) -> None:
    """Both cases commit the same username; leftover data would break the next."""
    assert db.execute("SELECT count(*) FROM users").fetchone() == (0,)
    assert db.execute("SELECT count(*) FROM auth_refresh_sessions").fetchone() == (0,)
    assert db.execute("SELECT count(*) FROM network_flows").fetchone() == (0,)
    db.execute(
        "INSERT INTO network_flows (flow_id, ts_start) VALUES (%s, %s)",
        ("00000000-0000-0000-0000-000000000001", "2026-01-01T00:00:00Z"),
    )
    create_user(username="same-user-each-test")

    response = client.post("/api/v1/auth/login", json={"username": "same-user-each-test", "password": PASSWORD})

    assert response.status_code == 200, response.text
    assert db.execute("SELECT count(*) FROM users").fetchone() == (1,)
    assert db.execute("SELECT count(*) FROM auth_refresh_sessions").fetchone() == (1,)
    assert db.execute("SELECT count(*) FROM network_flows").fetchone() == (1,)
