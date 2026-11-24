"""All detection routes enforce the existing Bearer access-token authentication."""

from datetime import timedelta
from uuid import uuid4

import pytest
from app.domain.user_role import UserRole
from app.features.auth.common.dependencies import get_auth
from fastapi.testclient import TestClient

DETECTION_ID = uuid4()
ROUTES = [
    "/api/v1/detections",
    f"/api/v1/detections/{DETECTION_ID}",
    f"/api/v1/detections/{DETECTION_ID}/flows",
]


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("token_kind", ["missing", "invalid", "expired", "refresh", "unknown_user"])
def test_detection_routes_reject_invalid_credentials(client: TestClient, route: str, token_kind: str):
    auth = get_auth()
    headers = {}
    if token_kind == "invalid":
        headers["Authorization"] = "Bearer invalid-token"
    elif token_kind == "expired":
        token = auth.create_access_token(uid=str(uuid4()), expiry=timedelta(seconds=-60))
        headers["Authorization"] = f"Bearer {token}"
    elif token_kind == "refresh":
        token = auth.create_token_pair(uid=str(uuid4())).refresh_token
        headers["Authorization"] = f"Bearer {token}"
    elif token_kind == "unknown_user":
        token = auth.create_access_token(uid=str(uuid4()))
        headers["Authorization"] = f"Bearer {token}"

    response = client.get(route, headers=headers)

    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_detection_routes_accept_access_tokens(client: TestClient, create_user, db, role: UserRole):
    user = create_user(role=role)
    login = client.post("/api/v1/auth/login", json={"username": user.username, "password": "test-password-12345"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    db.execute(
        "INSERT INTO detections (detection_id, created_at, type, method, severity) "
        "VALUES (%s, '2026-01-01T00:00:00Z', 'port_scan', 'rule', 'HIGH')",
        (DETECTION_ID,),
    )

    for route in ROUTES:
        response = client.get(route, headers=headers)
        assert response.status_code == 200, response.text


@pytest.mark.parametrize("route", ["/api/v1/detections", "/api/v1/detections/{id}", "/api/v1/detections/{id}/flows"])
def test_openapi_requires_bearer_access_token(client: TestClient, route: str):
    operation = client.get("/openapi.json").json()["paths"][route]["get"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert "401" in operation["responses"]
