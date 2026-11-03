"""Configuration HTTP contracts against real authentication and disposable TimescaleDB."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from app.domain.user_role import UserRole
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

URL = "/api/v1/detection-configurations"
BODY = {"detection_type": "port_scan", "method": "rule", "parameters": {"window_s": 10, "threshold": 100}}
OPERATIONS = [("GET", ""), ("GET", "/{id}"), ("POST", ""), ("PATCH", "/{id}"), ("PUT", "/{id}/activate")]


@pytest.fixture
def credentials(client: TestClient, create_user):
    def login(role=UserRole.ADMIN):
        create_user(role=role)
        response = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
        assert response.status_code == 200, response.text
        tokens = response.json()
        return {"Authorization": f"Bearer {tokens['access_token']}"}, tokens

    return login


@pytest.fixture
def admin_headers(credentials):
    return credentials()[0]


@pytest.fixture
def insert_configuration(db: psycopg.Connection):
    def insert(*, configuration_id=None, detection_type="port_scan", method="rule", parameters=None, active=False):
        configuration_id = configuration_id or uuid4()
        db.execute(
            "INSERT INTO detection_configs (configuration_id, detection_type, method, parameters, active) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                configuration_id,
                detection_type,
                method,
                Jsonb({"window_s": 10} if parameters is None else parameters),
                active,
            ),
        )
        return configuration_id

    return insert


def snapshot(db):
    return db.execute("SELECT * FROM detection_configs ORDER BY configuration_id").fetchall()


def body_for(method):
    return BODY if method == "POST" else {"parameters": {"threshold": 25}} if method == "PATCH" else None


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_both_roles_can_read_without_changing_data(client, db, credentials, insert_configuration, role) -> None:
    headers, _ = credentials(role)
    parameters = {"ports": [22, 3389], "nested": {"enabled": True, "optional": None}, "ratio": 1.25}
    configuration_id = insert_configuration(parameters=parameters, active=True)
    before = snapshot(db)
    expected = {
        "configuration_id": str(configuration_id),
        "detection_type": "port_scan",
        "method": "rule",
        "parameters": parameters,
        "active": True,
    }
    detail = client.get(f"{URL}/{configuration_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json() == expected
    listed = client.get(URL, headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == [expected]
    assert snapshot(db) == before


@pytest.mark.parametrize("page", [1, 2])
def test_empty_list(client, admin_headers, page) -> None:
    response = client.get(URL, params={"page": page}, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": 50,
        "total_pages": 0,
        "has_next": False,
        "has_previous": False,
    }


@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_stable_pagination_and_out_of_range_total(client, admin_headers, insert_configuration, sort_order) -> None:
    ids = [UUID(int=value) for value in range(1, 6)]
    for configuration_id in reversed(ids):
        insert_configuration(configuration_id=configuration_id)
    expected = ids if sort_order == "asc" else list(reversed(ids))
    collected = []
    for page in range(1, 5):
        response = client.get(
            URL, params={"page": page, "page_size": 2, "sort_order": sort_order}, headers=admin_headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["total"], body["page"], body["page_size"], body["total_pages"]) == (5, page, 2, 3)
        assert body["has_next"] is (page < 3)
        assert body["has_previous"] is (page > 1)
        actual = [UUID(item["configuration_id"]) for item in body["items"]]
        assert actual == expected[(page - 1) * 2 : page * 2]
        collected.extend(actual)
    assert collected == expected


@pytest.mark.parametrize(
    "filters, expected_indexes",
    [
        ({"detection_type": "port_scan"}, [0, 1]),
        ({"method": "statistical"}, [1, 2]),
        ({"active": "false"}, [1]),
        ({"active": "true"}, [0, 2]),
        ({"detection_type": "port_scan", "method": "statistical", "active": "false"}, [1]),
        ({"detection_type": "PORT_SCAN"}, []),
        ({"method": "missing"}, []),
    ],
)
def test_filters_apply_to_items_and_total(
    client, admin_headers, insert_configuration, filters, expected_indexes
) -> None:
    ids = [
        insert_configuration(configuration_id=UUID(int=1), active=True),
        insert_configuration(configuration_id=UUID(int=2), method="statistical"),
        insert_configuration(configuration_id=UUID(int=3), detection_type="dos", method="statistical", active=True),
    ]
    response = client.get(URL, params=filters, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == len(expected_indexes)
    assert [item["configuration_id"] for item in response.json()["items"]] == [str(ids[i]) for i in expected_indexes]


def test_create_persists_inactive_configuration_and_returns_location(client, db, admin_headers) -> None:
    body = {
        **BODY,
        "detection_type": " port_scan ",
        "method": " rule ",
        "parameters": {"window_s": 10, "nested": {"enabled": True, "optional": None}, "ports": [22, 3389]},
    }
    response = client.post(URL, json=body, headers=admin_headers)
    assert response.status_code == 201, response.text
    result = response.json()
    configuration_id = UUID(result["configuration_id"])
    assert result == {
        **body,
        "detection_type": "port_scan",
        "method": "rule",
        "configuration_id": str(configuration_id),
        "active": False,
    }
    assert response.headers["location"] == f"{URL}/{configuration_id}"
    assert db.execute(
        "SELECT detection_type, method, parameters, active FROM detection_configs WHERE configuration_id=%s",
        (configuration_id,),
    ).fetchone() == ("port_scan", "rule", body["parameters"], False)
    assert client.get(response.headers["location"], headers=admin_headers).json() == result
    assert client.get(URL, headers=admin_headers).json()["items"] == [result]


def test_create_allows_distinct_configurations_for_same_detection_and_method(client, admin_headers) -> None:
    first = client.post(URL, json=BODY, headers=admin_headers)
    second = client.post(URL, json=BODY, headers=admin_headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["configuration_id"] != second.json()["configuration_id"]


@pytest.mark.parametrize(
    "changes",
    [
        {"method": "statistical"},
        {"detection_type": "dos"},
        {"parameters": {"nested": {"new": True}}},
        {"parameters": {}},
    ],
)
def test_patch_replaces_only_supplied_fields_and_preserves_activation(
    client, db, admin_headers, insert_configuration, changes
) -> None:
    configuration_id = insert_configuration(active=True, parameters={"old": 10, "nested": {"old": True}})
    other_id = insert_configuration()
    before = client.get(f"{URL}/{configuration_id}", headers=admin_headers).json()
    other_before = db.execute("SELECT * FROM detection_configs WHERE configuration_id=%s", (other_id,)).fetchone()
    response = client.patch(f"{URL}/{configuration_id}", json=changes, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {**before, **changes}
    assert client.get(f"{URL}/{configuration_id}", headers=admin_headers).json() == response.json()
    assert (
        db.execute("SELECT * FROM detection_configs WHERE configuration_id=%s", (other_id,)).fetchone() == other_before
    )
    stored = db.execute(
        "SELECT method, detection_type, parameters, active FROM detection_configs WHERE configuration_id=%s",
        (configuration_id,),
    ).fetchone()
    assert stored == (response.json()["method"], response.json()["detection_type"], response.json()["parameters"], True)


def test_activation_is_idempotent_and_preserves_other_configurations(
    client, db, admin_headers, insert_configuration
) -> None:
    configuration_id = insert_configuration()
    other_id = insert_configuration(active=True)
    before = client.get(f"{URL}/{configuration_id}", headers=admin_headers).json()
    other_before = db.execute("SELECT * FROM detection_configs WHERE configuration_id=%s", (other_id,)).fetchone()
    first = client.put(f"{URL}/{configuration_id}/activate", headers=admin_headers)
    second = client.put(f"{URL}/{configuration_id}/activate", headers=admin_headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {**before, "active": True}
    assert db.execute(
        "SELECT active FROM detection_configs WHERE configuration_id=%s", (configuration_id,)
    ).fetchone() == (True,)
    assert (
        db.execute("SELECT * FROM detection_configs WHERE configuration_id=%s", (other_id,)).fetchone() == other_before
    )


def test_concurrent_activation_and_patch_do_not_lose_changes(client, db, admin_headers, insert_configuration) -> None:
    configuration_id = insert_configuration()

    def write(index):
        if index % 2:
            return client.patch(
                f"{URL}/{configuration_id}", json={"parameters": {"threshold": 25}}, headers=admin_headers
            )
        return client.put(f"{URL}/{configuration_id}/activate", headers=admin_headers)

    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(write, range(4)))
    assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
    assert db.execute(
        "SELECT parameters, active FROM detection_configs WHERE configuration_id=%s", (configuration_id,)
    ).fetchone() == ({"threshold": 25}, True)


@pytest.mark.parametrize("method, suffix", OPERATIONS)
@pytest.mark.parametrize("token_kind", ["missing", "malformed", "refresh", "deleted_user"])
def test_all_endpoints_reject_invalid_authentication(
    client, db, credentials, insert_configuration, method, suffix, token_kind
) -> None:
    headers, tokens = credentials()
    configuration_id = insert_configuration()
    before = snapshot(db)
    if token_kind == "missing":
        headers = {}
    elif token_kind == "malformed":
        headers = {"Authorization": "Bearer invalid-token"}
    elif token_kind == "refresh":
        headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    else:
        db.execute("DELETE FROM users")
    response = client.request(method, URL + suffix.format(id=configuration_id), json=body_for(method), headers=headers)
    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"
    assert snapshot(db) == before


@pytest.mark.parametrize("method, suffix", OPERATIONS[2:])
def test_regular_user_cannot_write(client, db, credentials, insert_configuration, method, suffix) -> None:
    headers, _ = credentials(UserRole.USER)
    configuration_id = insert_configuration()
    before = snapshot(db)
    response = client.request(method, URL + suffix.format(id=configuration_id), json=body_for(method), headers=headers)
    assert response.status_code == 403, response.text
    assert snapshot(db) == before


@pytest.mark.parametrize("method, suffix", [OPERATIONS[1], OPERATIONS[3], OPERATIONS[4]])
def test_missing_configuration_returns_404_without_changes(
    client, db, admin_headers, insert_configuration, method, suffix
) -> None:
    insert_configuration(active=True)
    before = snapshot(db)
    response = client.request(method, URL + suffix.format(id=uuid4()), json=body_for(method), headers=admin_headers)
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Detection configuration not found"}
    assert snapshot(db) == before


@pytest.mark.parametrize("method, suffix", [OPERATIONS[1], OPERATIONS[3], OPERATIONS[4]])
def test_invalid_uuid_returns_422(client, admin_headers, method, suffix) -> None:
    response = client.request(method, URL + suffix.format(id="invalid"), json=body_for(method), headers=admin_headers)
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["path", "id"]


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 101},
        {"active": "invalid"},
        {"sort_order": "invalid"},
        {"detection_type": " "},
        {"method": " "},
    ],
)
def test_invalid_list_query_returns_422(client, admin_headers, params) -> None:
    response = client.get(URL, params=params, headers=admin_headers)
    assert response.status_code == 422, response.text
    assert all(entry["loc"][0] == "query" for entry in response.json()["detail"])


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize(
    "invalid",
    [
        {"parameters": None},
        {"parameters": []},
        {"parameters": "text"},
        {"parameters": {"nested": ["bad\x00value"]}},
        {"method": " "},
        {"detection_type": "x" * 129},
        {"active": True},
        {"configuration_id": str(UUID(int=1))},
        {"unknown": 1},
    ],
)
def test_invalid_write_returns_422_and_never_changes_rows(
    client, db, admin_headers, insert_configuration, method, invalid
) -> None:
    configuration_id = insert_configuration()
    before = snapshot(db)
    body = {**BODY, **invalid} if method == "POST" else invalid
    path = URL if method == "POST" else f"{URL}/{configuration_id}"
    response = client.request(method, path, json=body, headers=admin_headers)
    assert response.status_code == 422, response.text
    assert snapshot(db) == before


def test_empty_patch_and_incomplete_create_are_rejected(client, db, admin_headers, insert_configuration) -> None:
    configuration_id = insert_configuration()
    before = snapshot(db)
    assert client.patch(f"{URL}/{configuration_id}", json={}, headers=admin_headers).status_code == 422
    assert client.post(URL, json={"method": "rule"}, headers=admin_headers).status_code == 422
    assert snapshot(db) == before


def test_openapi_documents_all_operations_and_security(client) -> None:
    schema = client.get("/openapi.json").json()
    for method, suffix in OPERATIONS:
        operation = schema["paths"][URL + suffix][method.lower()]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert {"401", "422", "503"} <= operation["responses"].keys()
        if method in {"POST", "PATCH", "PUT"}:
            assert "403" in operation["responses"]
        if "{id}" in suffix:
            assert "404" in operation["responses"]
        if method in {"POST", "PATCH"}:
            assert operation["requestBody"]["required"] is True
        else:
            assert "requestBody" not in operation
    assert "201" in schema["paths"][URL]["post"]["responses"]
    for name in ("CreateConfigurationRequest", "UpdateConfigurationRequest"):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False


@pytest.mark.parametrize("method, suffix", OPERATIONS)
def test_storage_errors_return_503_without_exposing_sql(client, db, admin_headers, method, suffix) -> None:
    # Break only this test's disposable schema; authentication still uses the real users table.
    db.execute("ALTER TABLE detection_configs RENAME TO unavailable_detection_configs")
    try:
        response = client.request(method, URL + suffix.format(id=uuid4()), json=body_for(method), headers=admin_headers)
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": "Database storage unavailable"}
    finally:
        db.execute("ALTER TABLE unavailable_detection_configs RENAME TO detection_configs")
