"""Security checks over every route of the API (test plan SEC-03 to SEC-06, NFR06).

The endpoint test files check authentication for their own routes. These tests go over all routes at once, so a new
route without a token check, or a query parameter that reaches the database unchecked, shows up here.
PUBLIC and PROTECTED together must list every operation of the OpenAPI schema (first test).
"""

import base64
import json
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import psycopg
import pytest
from app.domain.user_role import UserRole

START = datetime(2026, 11, 1, 12, tzinfo=UTC)
PASSWORD = "test-password-12345"

# answer without a token on purpose
PUBLIC = {("GET", "/health"), ("GET", "/health/ping"), ("POST", "/api/v1/auth/login")}

PROTECTED = [
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/auth/logout"),
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/dashboard/summary"),
    ("GET", "/api/v1/dashboard/timeseries"),
    ("GET", "/api/v1/alerts"),
    ("GET", "/api/v1/alerts/{id}"),
    ("PATCH", "/api/v1/alerts/{id}/acknowledge"),
    ("GET", "/api/v1/detections"),
    ("GET", "/api/v1/detections/{id}"),
    ("GET", "/api/v1/detections/{id}/flows"),
    ("GET", "/api/v1/flows"),
    ("GET", "/api/v1/flows/{flowId}"),
    ("GET", "/api/v1/detection-configurations"),
    ("POST", "/api/v1/detection-configurations"),
    ("GET", "/api/v1/detection-configurations/{id}"),
    ("PATCH", "/api/v1/detection-configurations/{id}"),
    ("PUT", "/api/v1/detection-configurations/{id}/activate"),
]
ADMIN_ONLY = [
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/detection-configurations"),
    ("PATCH", "/api/v1/detection-configurations/{id}"),
    ("PUT", "/api/v1/detection-configurations/{id}/activate"),
]
REFRESH_TOKEN_ROUTES = {("POST", "/api/v1/auth/refresh"), ("POST", "/api/v1/auth/logout")}

# The detection routes answer without a token for now ("No token needed for now" in their description), a defect in
# the test report. strict: when they get a token check these tests pass and the mark has to go.
OPEN_FOR_NOW = {
    ("GET", "/api/v1/detections"),
    ("GET", "/api/v1/detections/{id}"),
    ("GET", "/api/v1/detections/{id}/flows"),
}
OPEN_FOR_NOW_MARK = pytest.mark.xfail(strict=True, reason="detection routes don't check the token yet")

BODIES = {
    ("POST", "/api/v1/auth/register"): {"username": "new-user", "password": "new-password-12345"},
    ("POST", "/api/v1/detection-configurations"): {
        "detection_type": "port_scan",
        "method": "rule",
        "parameters": {"unique_dst_ports_threshold": 5},
    },
    ("PATCH", "/api/v1/detection-configurations/{id}"): {"parameters": {"unique_dst_ports_threshold": 5}},
}
QUERIES = {
    "/api/v1/dashboard/summary": {
        "start_time": START.isoformat(),
        "end_time": (START + timedelta(hours=1)).isoformat(),
    },
    "/api/v1/flows/{flowId}": {"tsStart": START.isoformat()},
}


def routes(names, marked=OPEN_FOR_NOW):
    return [
        pytest.param(method, path, marks=OPEN_FOR_NOW_MARK if (method, path) in marked else (), id=f"{method} {path}")
        for method, path in names
    ]


def send(client, method, path, token=None, record_id=None):
    """A request that would be valid apart from the token, so a refusal can only come from the token check."""
    url = path.replace("{id}", str(record_id or uuid4())).replace("{flowId}", str(uuid4()))
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.request(method, url, params=QUERIES.get(path), json=BODIES.get((method, path)), headers=headers)


def login(client, username):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def accounts(client, create_user):
    admin = create_user(username="sec-admin", password=PASSWORD, role=UserRole.ADMIN)
    user = create_user(username="sec-user", password=PASSWORD)
    return {"admin": (admin, login(client, "sec-admin")), "user": (user, login(client, "sec-user"))}


@pytest.fixture
def configuration_id(db: psycopg.Connection):
    configuration_id = uuid4()
    db.execute(
        "INSERT INTO detection_configs (configuration_id, detection_type, method, parameters, active) "
        "VALUES (%s, 'port_scan', 'rule', %s, false)",
        (configuration_id, json.dumps({"unique_dst_ports_threshold": 100})),
    )
    return configuration_id


def table_state(db: psycopg.Connection):
    return (
        db.execute("SELECT count(*) FROM users").fetchone()[0],
        db.execute("SELECT configuration_id, parameters, active FROM detection_configs ORDER BY 1").fetchall(),
    )


# ---- tokens an attacker can make without the key ----


def unpadded(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def claims_of(token: str) -> dict:
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def with_claims(token: str, **changes) -> str:
    """Other claims under the original header and signature."""
    header, _, signature = token.split(".")
    return f"{header}.{unpadded(json.dumps({**claims_of(token), **changes}).encode())}.{signature}"


def bad_token(kind: str, token: str, other_user_id) -> str:
    claims = claims_of(token)
    if kind == "expired":  # signed with the real key, but over
        return jwt.encode({**claims, "exp": int(time.time()) - 60}, os.environ["JWT_SECRET"], algorithm="HS256")
    if kind == "other_user":
        return with_claims(token, sub=str(other_user_id))
    if kind == "wrong_key":
        return jwt.encode(claims, "not-the-server-key-" + "x" * 32, algorithm="HS256")
    if kind == "alg_none":  # no signature at all
        header = unpadded(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        return f"{header}.{token.split('.')[1]}."
    raise ValueError(kind)


# ---- tests ----


def test_routes_cover_the_whole_api(client) -> None:
    """A new route has to be added to PUBLIC or PROTECTED, so the tests below go over it too."""
    schema = client.get("/openapi.json").json()
    operations = {(method.upper(), path) for path, item in schema["paths"].items() for method in item}
    assert operations == PUBLIC | set(PROTECTED)


@pytest.mark.parametrize(("method", "path"), routes(PROTECTED))
def test_request_without_a_token_is_refused(client, method, path) -> None:
    """SEC-03"""
    response = send(client, method, path)
    assert response.status_code == 401, response.text
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize(("method", "path"), routes(ADMIN_ONLY))
def test_regular_user_cannot_use_admin_operations(client, db, accounts, configuration_id, method, path) -> None:
    """SEC-04: refused with 403 and nothing changes."""
    before = table_state(db)
    response = send(client, method, path, accounts["user"][1]["access_token"], record_id=configuration_id)
    assert response.status_code == 403, response.text
    assert table_state(db) == before


@pytest.mark.parametrize("kind", ["expired", "other_user", "wrong_key", "alg_none"])
@pytest.mark.parametrize(("method", "path"), routes(PROTECTED))
def test_tampered_or_expired_token_is_refused(client, accounts, method, path, kind) -> None:
    """SEC-05: an expired token, the user id of someone else under the old signature, a token signed with another
    key and an unsigned token ("alg": "none")."""
    admin, _ = accounts["admin"]
    _, tokens = accounts["user"]
    token = tokens["refresh_token"] if (method, path) in REFRESH_TOKEN_ROUTES else tokens["access_token"]
    response = send(client, method, path, bad_token(kind, token, admin.user_id))
    assert response.status_code == 401, response.text


def test_user_cannot_become_admin_by_editing_the_token(client, db, accounts) -> None:
    """SEC-05: the user puts the admin's id into the token and tries an admin operation."""
    admin, _ = accounts["admin"]
    _, tokens = accounts["user"]
    before = table_state(db)
    response = send(
        client, "POST", "/api/v1/detection-configurations", with_claims(tokens["access_token"], sub=str(admin.user_id))
    )
    assert response.status_code == 401, response.text
    assert table_state(db) == before


INJECTIONS = [
    "' OR '1'='1",
    "1' OR 1=1 --",
    "'; DROP TABLE users; --",
    '" OR ""="',
    "%' OR '%'='",
    "\\",
    "<script>alert(1)</script>",
    "../../../../etc/passwd",
    "a" * 5000,
    "".join(map(chr, (0x540D, 0x524D, 0x1F600))),  # non-ASCII text
]
# text in a response that would mean the database or a stack trace leaked out
LEAKS = ("psycopg", "sqlalchemy", "syntax error", "traceback", "postgres", "pg_catalog")
QUERY_PARAMETERS = [
    ("/api/v1/alerts", "status"),
    ("/api/v1/alerts", "severity"),
    ("/api/v1/alerts", "detection_type"),
    ("/api/v1/alerts", "src_ip"),
    ("/api/v1/alerts", "protocol"),
    ("/api/v1/alerts", "sort_order"),
    ("/api/v1/alerts", "start_time"),
    ("/api/v1/detections", "severity"),
    ("/api/v1/detections", "detection_type"),
    ("/api/v1/detections", "method"),
    ("/api/v1/detections", "dst_ip"),
    ("/api/v1/detections", "protocol"),
    ("/api/v1/flows", "src_ip"),
    ("/api/v1/flows", "dst_port"),
    ("/api/v1/flows", "protocol"),
    ("/api/v1/flows", "end_time"),
    ("/api/v1/detection-configurations", "detection_type"),
    ("/api/v1/detection-configurations", "method"),
    ("/api/v1/dashboard/timeseries", "interval"),
]


@pytest.fixture
def stored_rows(db: psycopg.Connection, configuration_id):
    """One row in every table a list reads, so a filter that was turned into "true" would return it."""
    detection_id = uuid4()
    db.execute(
        "INSERT INTO detections (detection_id, created_at, type, method, severity, src_ip, dst_ip, protocol) "
        "VALUES (%s, %s, 'port_scan', 'rule', 'HIGH', '192.0.2.1', '198.51.100.7', 'TCP')",
        (detection_id, START),
    )
    db.execute(
        "INSERT INTO alerts (alert_id, detection_id, created_at, status) VALUES (%s, %s, %s, 'NEW')",
        (uuid4(), detection_id, START),
    )
    db.execute(
        "INSERT INTO network_flows (flow_id, ts_start, src_ip, dst_ip, src_port, dst_port, protocol) "
        "VALUES (%s, %s, '192.0.2.1', '198.51.100.7', 40000, 22, 'TCP')",
        (uuid4(), START),
    )


@pytest.mark.parametrize(("path", "parameter"), QUERY_PARAMETERS, ids=[f"{p} {q}" for p, q in QUERY_PARAMETERS])
def test_injection_strings_in_query_parameters(client, db, accounts, stored_rows, path, parameter) -> None:
    """SEC-06: 422 or an empty result, never 500, and nothing from the database in the response."""
    headers = {"Authorization": f"Bearer {accounts['admin'][1]['access_token']}"}
    for value in INJECTIONS:
        response = client.get(path, params={parameter: value}, headers=headers)
        assert response.status_code in (200, 422), f"{value!r}: {response.status_code} {response.text[:300]}"
        body = response.text.lower()
        assert not [leak for leak in LEAKS if leak in body], f"{value!r}: {response.text[:300]}"
        if response.status_code == 200 and "items" in response.json():
            assert response.json()["items"] == [], f"{value!r} matched stored rows"
    assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 2
