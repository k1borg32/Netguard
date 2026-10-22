"""Flow endpoints through real HTTP, JWT, SQLAlchemy and TimescaleDB."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
import pytest
from app.domain.user_role import UserRole
from fastapi.testclient import TestClient

URL = "/api/v1/flows"
START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=1)


@pytest.fixture
def tokens(client: TestClient, create_user) -> dict[str, str]:
    create_user()
    response = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def headers(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def insert_flow(
    db: psycopg.Connection,
    *,
    flow_id: UUID | None = None,
    ts_start: datetime = START,
    src_ip: str = "192.0.2.1",
    dst_ip: str = "198.51.100.2",
    src_port: int = 12345,
    dst_port: int = 443,
    protocol: str = "TCP",
) -> UUID:
    flow_id = flow_id if flow_id is not None else uuid4()
    db.execute(
        "INSERT INTO network_flows "
        "(flow_id, ts_start, src_ip, dst_ip, src_port, dst_port, protocol, trace_id, ingested_at, "
        "duration_ms, packets, bytes, tcp_flags, source, label) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'trace-test', %s, 12.5, 7, 1024, 'S', 'simulator', 'benign')",
        (flow_id, ts_start, src_ip, dst_ip, src_port, dst_port, protocol, END),
    )
    return flow_id


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_both_endpoints_allow_both_roles(
    client: TestClient, db: psycopg.Connection, create_user, role: UserRole
) -> None:
    create_user(role=role)
    login = client.post("/api/v1/auth/login", json={"username": "test-user", "password": "test-password-12345"})
    assert login.status_code == 200, login.text
    request_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    flow_id = insert_flow(db)

    listing = client.get(URL, headers=request_headers)
    detail = client.get(f"{URL}/{flow_id}", params={"tsStart": START.isoformat()}, headers=request_headers)

    assert listing.status_code == 200, listing.text
    assert detail.status_code == 200, detail.text
    assert listing.json()["items"] == [detail.json()]


def test_empty_list_and_page_beyond_results_keep_total(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    empty = client.get(URL, headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"items": [], "total": 0, "page": 1, "page_size": 50}
    insert_flow(db)

    response = client.get(URL, params={"page": 2, "page_size": 1}, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 1, "page": 2, "page_size": 1}


@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_pagination_has_stable_order_with_timestamp_ties_and_repeated_uuids(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str], sort_order: str
) -> None:
    keys = [(START, UUID(int=2)), (START, UUID(int=1)), (END, UUID(int=1)), (END, UUID(int=3))]
    for timestamp, flow_id in keys:
        insert_flow(db, flow_id=flow_id, ts_start=timestamp)
    observed = []
    for page in (1, 2):
        response = client.get(URL, params={"page": page, "page_size": 2, "sort_order": sort_order}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["total"], body["page"], body["page_size"]) == (4, page, 2)
        observed.extend((datetime.fromisoformat(item["ts_start"]), UUID(item["flow_id"])) for item in body["items"])

    assert observed == sorted(keys, reverse=sort_order == "desc")


def test_default_order_is_newest_first(client: TestClient, db: psycopg.Connection, headers: dict[str, str]) -> None:
    insert_flow(db, ts_start=START)
    newest = insert_flow(db, ts_start=END)

    response = client.get(URL, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["flow_id"] == str(newest)


def test_time_filters_use_half_open_start_time_range(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    delta = timedelta(microseconds=1)
    keys = [(timestamp, insert_flow(db, ts_start=timestamp)) for timestamp in (START - delta, START, END - delta, END)]
    response = client.get(
        URL,
        params={"start_time": "2026-01-01T01:00:00+01:00", "end_time": END.isoformat(), "sort_order": "asc"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert [item["flow_id"] for item in response.json()["items"]] == [str(key[1]) for key in keys[1:3]]


@pytest.mark.parametrize(
    "params",
    [
        {"start_time": START.isoformat()},
        {"end_time": END.isoformat()},
        {"src_ip": "192.0.2.1"},
        {"dst_ip": "198.51.100.2"},
        {"src_port": 12345},
        {"dst_port": 443},
        {"protocol": "TCP"},
    ],
)
def test_each_filter_is_applied(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str], params: dict
) -> None:
    expected = insert_flow(db)
    insert_flow(
        db,
        ts_start=START - timedelta(days=1) if "start_time" in params else END,
        src_ip="192.0.2.99",
        dst_ip="198.51.100.99",
        src_port=53,
        dst_port=80,
        protocol="UDP",
    )

    response = client.get(URL, params=params, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [item["flow_id"] for item in response.json()["items"]] == [str(expected)]


def test_filters_are_combined_and_total_counts_only_matches(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    expected = insert_flow(db, src_port=0)
    insert_flow(db, src_port=0, protocol="UDP")
    insert_flow(db, src_port=0, dst_ip="198.51.100.99")
    insert_flow(db, src_port=0, ts_start=END)
    insert_flow(db, src_port=12345)
    response = client.get(
        URL,
        params={
            "start_time": START.isoformat(),
            "end_time": END.isoformat(),
            "src_ip": "192.0.2.1",
            "dst_ip": "198.51.100.2",
            "src_port": 0,
            "dst_port": 443,
            "protocol": "TCP",
            "page_size": 1,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [item["flow_id"] for item in response.json()["items"]] == [str(expected)]


def test_ipv6_filters_match_equivalent_addresses(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    expected = insert_flow(db, src_ip="2001:db8::1", dst_ip="::1")
    insert_flow(db)

    response = client.get(URL, params={"src_ip": "2001:0db8:0:0:0:0:0:1", "dst_ip": "::1"}, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["flow_id"] == str(expected)
    assert response.json()["items"][0]["src_ip"] == "2001:db8::1"


def test_exact_protocol_and_empty_filtered_result(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    insert_flow(db, protocol="TCP")

    response = client.get(URL, params={"protocol": "tcp"}, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 50}


def test_detail_uses_both_key_parts_and_returns_all_fields(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    flow_id = insert_flow(db)
    insert_flow(db, flow_id=flow_id, ts_start=END, protocol="UDP")

    response = client.get(f"{URL}/{flow_id}", params={"tsStart": "2026-01-01T01:00:00+01:00"}, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "flow_id": str(flow_id),
        "ts_start": "2026-01-01T00:00:00Z",
        "trace_id": "trace-test",
        "ingested_at": "2026-01-02T00:00:00Z",
        "duration_ms": 12.5,
        "src_ip": "192.0.2.1",
        "dst_ip": "198.51.100.2",
        "src_port": 12345,
        "dst_port": 443,
        "protocol": "TCP",
        "packets": 7,
        "bytes": 1024,
        "tcp_flags": "S",
        "source": "simulator",
        "label": "benign",
    }
    other = client.get(f"{URL}/{flow_id}", params={"tsStart": END.isoformat()}, headers=headers)
    assert other.status_code == 200, other.text
    assert other.json()["protocol"] == "UDP"
    assert db.execute("SELECT count(*) FROM network_flows").fetchone() == (2,)


def test_nullable_flow_fields_in_list_and_detail(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str]
) -> None:
    flow_id = uuid4()
    db.execute("INSERT INTO network_flows (flow_id, ts_start) VALUES (%s, %s)", (flow_id, START))

    detail = client.get(f"{URL}/{flow_id}", params={"tsStart": START.isoformat()}, headers=headers)
    listing = client.get(URL, headers=headers)

    assert detail.status_code == 200, detail.text
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"] == [detail.json()]
    assert all(value is None for key, value in detail.json().items() if key not in {"flow_id", "ts_start"})


@pytest.mark.parametrize("missing_part", ["uuid", "timestamp"])
def test_detail_returns_404_for_a_missing_composite_key(
    client: TestClient, db: psycopg.Connection, headers: dict[str, str], missing_part: str
) -> None:
    flow_id = insert_flow(db)
    response = client.get(
        f"{URL}/{uuid4() if missing_part == 'uuid' else flow_id}",
        params={"tsStart": (START if missing_part == "uuid" else END).isoformat()},
        headers=headers,
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Flow not found"}


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"page": 0}, "page"),
        ({"page_size": 101}, "page_size"),
        ({"sort_order": "invalid"}, "sort_order"),
        ({"src_ip": "invalid"}, "src_ip"),
        ({"dst_ip": "192.0.2.0/24"}, "dst_ip"),
        ({"src_port": -1}, "src_port"),
        ({"dst_port": 65536}, "dst_port"),
        ({"protocol": ""}, "protocol"),
        ({"start_time": "2026-01-01T00:00:00"}, "start_time"),
        ({"end_time": "invalid"}, "end_time"),
        ({"start_time": START.isoformat(), "end_time": START.isoformat()}, "end_time"),
        ({"start_time": END.isoformat(), "end_time": START.isoformat()}, "end_time"),
    ],
)
def test_list_invalid_parameters_return_422(
    client: TestClient, headers: dict[str, str], params: dict, field: str
) -> None:
    response = client.get(URL, params=params, headers=headers)

    assert response.status_code == 422, response.text
    assert any(error["loc"] == ["query", field] for error in response.json()["detail"])


@pytest.mark.parametrize(
    ("identifier", "params", "location"),
    [
        ("invalid", {"tsStart": START.isoformat()}, ["path", "flowId"]),
        (str(UUID(int=1)), {}, ["query", "tsStart"]),
        (str(UUID(int=1)), {"tsStart": "invalid"}, ["query", "tsStart"]),
        (str(UUID(int=1)), {"tsStart": "2026-01-01T00:00:00"}, ["query", "tsStart"]),
        (str(UUID(int=1)), {"ts_start": START.isoformat()}, ["query", "tsStart"]),
    ],
)
def test_detail_invalid_parameters_return_422(
    client: TestClient, headers: dict[str, str], identifier: str, params: dict, location: list[str]
) -> None:
    response = client.get(f"{URL}/{identifier}", params=params, headers=headers)

    assert response.status_code == 422, response.text
    assert any(error["loc"] == location for error in response.json()["detail"])


@pytest.mark.parametrize("detail", [False, True])
@pytest.mark.parametrize("token_kind", ["missing", "malformed", "refresh", "deleted_user"])
def test_both_endpoints_reject_invalid_authentication(
    client: TestClient, db: psycopg.Connection, tokens: dict[str, str], detail: bool, token_kind: str
) -> None:
    request_headers = {}
    if token_kind == "malformed":
        request_headers = {"Authorization": "Bearer invalid-token"}
    elif token_kind == "refresh":
        request_headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    elif token_kind == "deleted_user":
        db.execute("DELETE FROM users")
        request_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client.get(
        f"{URL}/{uuid4()}" if detail else URL,
        params={"tsStart": START.isoformat()} if detail else {},
        headers=request_headers,
    )

    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"


def test_openapi_documents_both_routes_filters_and_authentication(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    listing = schema["paths"][URL]["get"]
    detail = schema["paths"][URL + "/{flowId}"]["get"]

    assert {parameter["name"] for parameter in listing["parameters"]} == {
        "start_time",
        "end_time",
        "src_ip",
        "dst_ip",
        "src_port",
        "dst_port",
        "protocol",
        "sort_order",
        "page",
        "page_size",
    }
    assert all(parameter["in"] == "query" and not parameter["required"] for parameter in listing["parameters"])
    assert {(parameter["name"], parameter["in"], parameter["required"]) for parameter in detail["parameters"]} == {
        ("flowId", "path", True),
        ("tsStart", "query", True),
    }
    for operation in (listing, detail):
        assert operation["security"] == [{"HTTPBearer": []}]
        assert "requestBody" not in operation
        assert {"200", "401", "422", "503"} <= set(operation["responses"])
    assert "404" in detail["responses"]
