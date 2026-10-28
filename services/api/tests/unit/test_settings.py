"""Container-safe configuration must not discover or load a repository .env."""

import asyncio

import pytest
from app.infrastructure.config import Settings
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_environment_is_sufficient_from_any_working_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql://netguard:example@db:5432/netguard")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    (tmp_path / ".env").write_text("DATABASE_URL=invalid\nJWT_SECRET=wrong\n", encoding="utf-8")

    settings = Settings()
    assert settings.database_url == "postgresql://netguard:example@db:5432/netguard"
    assert settings.jwt_secret.get_secret_value() == "test-secret"


def test_local_dotenv_does_not_replace_missing_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql://dotenv/ignored\n", encoding="utf-8")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert "database_url" in {item["loc"][0] for item in error.value.errors()}


@pytest.mark.parametrize("missing", [("DATABASE_URL",), ("JWT_SECRET",), ("DATABASE_URL", "JWT_SECRET")])
def test_api_rejects_missing_configuration_at_startup_without_exposing_values(monkeypatch, missing) -> None:
    from app.app import create_app

    secret = "private-test-secret-do-not-log"
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:private-password@localhost/test")
    monkeypatch.setenv("JWT_SECRET", secret)
    for name in missing:
        monkeypatch.delenv(name, raising=False)

    with (
        pytest.raises(RuntimeError) as error,
        TestClient(create_app(), backend_options={"loop_factory": asyncio.SelectorEventLoop}),
    ):
        pytest.fail("The API must not start without required settings")

    for name in missing:
        assert name in str(error.value)
    assert "python run.py" in str(error.value)
    assert secret not in str(error.value)
    assert "private-password" not in str(error.value)
